"""Trusted application boundary; never accept actor identity from request bodies."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import OperationalError


class ServiceError(Exception):
    def __init__(self, code, **details):
        self.code, self.details = code, details
        super().__init__(code)


def identifier(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError):
        raise ServiceError('validation_error', field='id') from None


def row(c, sql, **values):
    result = c.execute(text(sql), values).mappings().first()
    if result is None:
        raise ServiceError('not_found')
    return dict(result)


def _timestamp_cursor(value):
    if value is None:
        return None
    if not isinstance(value, (tuple, list)) or len(value) != 2 or not isinstance(value[0], str):
        raise ServiceError('validation_error', field='cursor')
    return value[0], identifier(value[1])


class Notebook:
    """One instance per trusted authenticated actor, not a public HTTP API."""

    def __init__(self, engine, actor_id):
        self.engine, self.actor = engine, identifier(actor_id)

    def _authorize(self, c):
        if not c.execute(text('SELECT 1 FROM users WHERE id=:id'), {'id': self.actor}).first():
            raise ServiceError('authentication_required')

    def _project(self, c, project_id):
        return row(c, 'SELECT * FROM projects WHERE id=:id AND owner_id=:owner', id=identifier(project_id), owner=self.actor)

    def _note(self, c, note_id):
        return row(c, '''SELECT n.*, r.revision_number, r.title, r.body_markdown,
                   r.content_format, r.content_schema_version
                   FROM notes n JOIN note_revisions r ON r.id=n.current_revision_id
                   WHERE n.id=:id AND n.owner_id=:owner''', id=identifier(note_id), owner=self.actor)

    def _revision(self, c, note_id, revision_id):
        self._note(c, note_id)
        return row(c, 'SELECT * FROM note_revisions WHERE note_id=:note AND id=:id', note=note_id, id=identifier(revision_id))

    def get_note(self, note_id):
        try:
            with self.engine.connect() as c:
                self._authorize(c)
                return self._note(c, note_id)
        except OperationalError:
            raise ServiceError('temporarily_unavailable') from None

    def get_revision(self, note_id, revision_id):
        try:
            with self.engine.connect() as c:
                self._authorize(c)
                return self._revision(c, identifier(note_id), revision_id)
        except OperationalError:
            raise ServiceError('temporarily_unavailable') from None

    def list_projects(self, limit=25, after=None):
        return self._list('projects', limit, after)

    def list_notes(self, project_id, trashed=False, limit=25, after=None):
        return self._list('notes', limit, after, project_id, trashed)

    def list_revisions(self, note_id, limit=25, after=None):
        return self._list('revisions', limit, after, note_id)

    def _list(self, kind, limit, after, scope=None, trashed=False):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ServiceError('validation_error', field='limit')
        try:
            with self.engine.connect() as c:
                self._authorize(c)
                values = {'owner': self.actor, 'limit': limit}
                if kind == 'projects':
                    cursor = _timestamp_cursor(after)
                    sql = 'SELECT * FROM projects WHERE owner_id=:owner'
                    if cursor:
                        values.update(after_time=cursor[0], after_id=cursor[1])
                        sql += ' AND (updated_at<:after_time OR (updated_at=:after_time AND id<:after_id))'
                    sql += ' ORDER BY updated_at DESC,id DESC LIMIT :limit'
                elif kind == 'revisions':
                    self._note(c, scope)
                    values['scope'] = identifier(scope)
                    if after is not None and (type(after) is not int or after < 1):
                        raise ServiceError('validation_error', field='cursor')
                    sql = '''SELECT id,note_id,revision_number,created_at,actor_type,actor_id,restored_from_revision_id
                             FROM note_revisions WHERE note_id=:scope'''
                    if after is not None:
                        values['after_number'] = after
                        sql += ' AND revision_number<:after_number'
                    sql += ' ORDER BY revision_number DESC LIMIT :limit'
                else:
                    cursor = _timestamp_cursor(after)
                    values['deleted'] = int(trashed)
                    sql = '''SELECT n.id,n.project_id,n.version,n.updated_at,n.deleted_at,r.title
                             FROM notes n JOIN note_revisions r ON r.id=n.current_revision_id
                             WHERE n.owner_id=:owner AND (n.deleted_at IS NOT NULL)=:deleted'''
                    if scope is not None:
                        self._project(c, scope)
                        values['scope'] = identifier(scope)
                        sql += ' AND n.project_id=:scope'
                    if cursor:
                        values.update(after_time=cursor[0], after_id=cursor[1])
                        sql += ' AND (n.updated_at<:after_time OR (n.updated_at=:after_time AND n.id<:after_id))'
                    sql += ' ORDER BY n.updated_at DESC,n.id DESC LIMIT :limit'
                return [dict(r) for r in c.execute(text(sql), values).mappings()]
        except OperationalError:
            raise ServiceError('temporarily_unavailable') from None

    def execute(self, operation, key, request_id=None, **payload):
        fields = {
            'create_project': ({'name'}, {'description'}),
            'rename_project': ({'project_id', 'expected_version', 'name'}, set()),
            'create_note': (set(), {'project_id', 'title', 'body_markdown'}),
            'update_note': ({'note_id', 'expected_version', 'title', 'body_markdown'}, set()),
            'move_note': ({'note_id', 'expected_version', 'destination_project_id'}, set()),
            'trash_note': ({'note_id', 'expected_version'}, set()),
            'restore_note': ({'note_id', 'expected_version'}, set()),
            'restore_revision': ({'note_id', 'expected_version', 'revision_id'}, set()),
        }
        if operation not in fields:
            raise ServiceError('validation_error', field='operation')
        required, optional = fields[operation]
        if not required <= payload.keys() or payload.keys() - required - optional:
            raise ServiceError('validation_error', field='payload')
        key = identifier(key)
        request_id = identifier(request_id or uuid4())
        p = dict(payload)
        for field in p:
            if field.endswith('_id'):
                p[field] = identifier(p[field])
        if 'expected_version' in p and (type(p['expected_version']) is not int or p['expected_version'] < 1):
            raise ServiceError('validation_error', field='expected_version')
        if operation in ('create_note', 'update_note'):
            for field, default in [('title', 'Untitled'), ('body_markdown', '')]:
                value = p.get(field, default)
                if not isinstance(value, str):
                    raise ServiceError('validation_error', field=field)
                p[field] = value.replace('\r\n', '\n')
            if not p['title'].strip():
                p['title'] = 'Untitled'
            if len(p['title']) > 200 or len(p['body_markdown'].encode()) > 1048576:
                raise ServiceError('payload_too_large')
        if operation in ('create_project', 'rename_project'):
            if not isinstance(p['name'], str) or not 1 <= len(p['name'].strip()) <= 200:
                raise ServiceError('validation_error', field='name')
            p['name'] = p['name'].strip()
        if operation == 'create_project':
            p.setdefault('description', '')
            if not isinstance(p['description'], str) or len(p['description']) > 2000:
                raise ServiceError('validation_error', field='description')
        try:
            with self.engine.connect() as c:
                c.exec_driver_sql('BEGIN IMMEDIATE')
                try:
                    self._authorize(c)
                    if operation == 'create_note' and 'project_id' not in p:
                        p['project_id'] = row(c, 'SELECT id FROM projects WHERE owner_id=:owner AND is_inbox=1', owner=self.actor)['id']
                    if 'note_id' in p:
                        self._note(c, p['note_id'])
                    for field in ('project_id', 'destination_project_id'):
                        if field in p:
                            self._project(c, p[field])
                    digest = hashlib.sha256(json.dumps([operation, p], sort_keys=True).encode()).hexdigest()
                    now = datetime.now(timezone.utc)
                    receipt = c.execute(text('SELECT * FROM mutation_receipts WHERE actor_id=:actor AND idempotency_key=:key'), {'actor': self.actor, 'key': key}).mappings().first()
                    if receipt and receipt['expires_at'] > now.isoformat():
                        if receipt['request_hash'] != digest:
                            raise ServiceError('idempotency_conflict')
                        c.rollback()
                        return json.loads(receipt['result_json'])
                    result = self._mutate(c, operation, p, now.isoformat(), request_id)
                    c.execute(text('DELETE FROM mutation_receipts WHERE actor_id=:actor AND idempotency_key=:key'), {'actor': self.actor, 'key': key})
                    c.execute(text('INSERT INTO mutation_receipts VALUES (:actor,:key,:op,:hash,:result,:now,:expiry)'), {'actor': self.actor, 'key': key, 'op': operation, 'hash': digest, 'result': json.dumps(result), 'now': now.isoformat(), 'expiry': (now + timedelta(days=7)).isoformat()})
                    c.commit()
                    return result
                except Exception:
                    c.rollback()
                    raise
        except OperationalError:
            raise ServiceError('temporarily_unavailable') from None

    def _mutate(self, c, op, p, now, request):
        note = None
        project = None
        changed = True
        before = None
        if op == 'create_project':
            project = str(uuid4())
            c.execute(text('INSERT INTO projects VALUES (:id,:owner,:name,:description,0,1,:now,:now)'), dict(p, id=project, owner=self.actor, now=now))
            version = 1
        elif op == 'rename_project':
            old = self._project(c, p['project_id'])
            self._version(old, p)
            project = old['id']
            changed = old['name'] != p['name']
            version = old['version'] + int(changed)
            if changed:
                c.execute(text('UPDATE projects SET name=:name,version=:version,updated_at=:now WHERE id=:id'), {'name': p['name'], 'version': version, 'now': now, 'id': project})
        elif op == 'create_note':
            note, revision = str(uuid4()), str(uuid4())
            project = p['project_id']
            c.execute(text("INSERT INTO notes VALUES (:id,:owner,:project,:revision,1,2,:now,:now,NULL)"), {'id': note, 'owner': self.actor, 'project': project, 'revision': revision, 'now': now})
            self._insert_revision(c, note, revision, 1, p, now, request)
        else:
            old = self._note(c, p['note_id'])
            self._version(old, p)
            note, project = old['id'], old['project_id']
            if old['deleted_at'] and op not in ('restore_note', 'trash_note'):
                raise ServiceError('invalid_state')
            if op in ('update_note', 'restore_revision'):
                content = p if op == 'update_note' else self._revision(c, note, p['revision_id'])
                changed = op == 'restore_revision' or any(old[k] != content[k] for k in ('title', 'body_markdown'))
                if changed:
                    revision = str(uuid4())
                    before = old['current_revision_id']
                    self._insert_revision(c, note, revision, old['next_revision_number'], content, now, request, p.get('revision_id'))
                    c.execute(text('UPDATE notes SET current_revision_id=:revision,next_revision_number=next_revision_number+1 WHERE id=:id'), {'revision': revision, 'id': note})
            elif op == 'move_note':
                changed = project != p['destination_project_id']
                if changed:
                    before = project
                    project = p['destination_project_id']
                    c.execute(text('UPDATE notes SET project_id=:project WHERE id=:id'), {'project': project, 'id': note})
            else:
                deleted = now if op == 'trash_note' else None
                changed = bool(old['deleted_at']) != bool(deleted)
                if changed:
                    c.execute(text('UPDATE notes SET deleted_at=:deleted WHERE id=:id'), {'deleted': deleted, 'id': note})
            if changed:
                c.execute(text('UPDATE notes SET version=version+1,updated_at=:now WHERE id=:id'), {'now': now, 'id': note})
        if changed:
            c.execute(text('INSERT INTO audit_events VALUES (:id,:note,:project,:op,\'user\',:actor,:request,:now,1,:details)'), {'id': str(uuid4()), 'note': note, 'project': project, 'op': op, 'actor': self.actor, 'request': request, 'now': now, 'details': json.dumps({'previous_id': before, 'source_revision_id': p.get('revision_id')})})
        if note:
            current = self._note(c, note)
            return {k: current[k] for k in ('id', 'project_id', 'version', 'current_revision_id', 'revision_number', 'updated_at')} | {'changed': changed}
        return {'id': project, 'version': version, 'changed': changed}

    @staticmethod
    def _version(old, payload):
        if old['version'] != payload['expected_version']:
            raise ServiceError('version_conflict', current_version=old['version'], current_revision_id=old.get('current_revision_id'))

    def _insert_revision(self, c, note, revision, number, content, now, request, restored=None):
        c.execute(text("INSERT INTO note_revisions VALUES (:id,:note,:number,:title,'markdown',1,:body,'user',:actor,'manual',:request,:now,:restored)"), {'id': revision, 'note': note, 'number': number, 'title': content['title'], 'body': content['body_markdown'], 'actor': self.actor, 'request': request, 'now': now, 'restored': restored})
