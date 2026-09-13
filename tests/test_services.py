from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from local_ai_notes.cli import create_owner
from local_ai_notes.services import Notebook, ServiceError
from test_foundation import db  # noqa: F401


def key():
    return str(uuid4())


@pytest.fixture
def book(db):
    return Notebook(db, create_owner(db, 'owner', 'synthetic password'))


def test_note_lifecycle_and_restore(book):
    first = book.execute('create_note', key(), body_markdown='original')
    note = first['id']
    edited = book.execute('update_note', key(), note_id=note, expected_version=1,
                          title='Changed', body_markdown='new')
    project = book.execute('create_project', key(), name='Work')['id']
    moved = book.execute('move_note', key(), note_id=note, expected_version=2, destination_project_id=project)
    assert moved['current_revision_id'] == edited['current_revision_id']
    restored = book.execute('restore_revision', key(), note_id=note, expected_version=3,
                            revision_id=first['current_revision_id'])
    assert restored['project_id'] == project
    assert book.get_note(note)['body_markdown'] == 'original'
    assert len(book.list_revisions(note)) == 3
    book.execute('trash_note', key(), note_id=note, expected_version=4)
    assert book.list_notes(project) == []
    assert len(book.list_notes(project, trashed=True)) == 1
    with pytest.raises(ServiceError, match='invalid_state'):
        book.execute('move_note', key(), note_id=note, expected_version=5, destination_project_id=project)
    book.execute('restore_note', key(), note_id=note, expected_version=5)
    assert len(book.list_notes(project)) == 1


def test_retry_and_noop(book):
    request = key()
    first = book.execute('create_note', request)
    assert book.execute('create_note', request) == first
    with pytest.raises(ServiceError, match='idempotency_conflict'):
        book.execute('create_note', request, title='Other')
    result = book.execute('update_note', key(), note_id=first['id'], expected_version=1,
                          title='Untitled', body_markdown='')
    assert not result['changed'] and result['version'] == 1
    assert len(book.list_revisions(first['id'])) == 1
    assert result['updated_at'] == first['updated_at']


def test_concurrent_edit_and_duplicate_request(book):
    note = book.execute('create_note', key())['id']
    def edit(title):
        try:
            return book.execute('update_note', key(), note_id=note, expected_version=1, title=title, body_markdown='')
        except ServiceError as error:
            return error.code
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(edit, ['A', 'B']))
    assert sum(r == 'version_conflict' for r in results) == 1
    request = key()
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: book.execute('create_note', request), range(2)))
    assert results[0] == results[1]


def test_scope_validation_and_unknown_actor(book):
    inbox = book.list_projects()[0]['id']
    other = book.execute('create_project', key(), name='Other')['id']
    book.execute('create_note', key(), project_id=other)
    assert book.list_notes(inbox) == []
    assert len(book.list_notes(None)) == 1
    with pytest.raises(ServiceError, match='not_found'):
        book.execute('create_note', key(), project_id=key())
    with pytest.raises(ServiceError, match='authentication_required'):
        Notebook(book.engine, key()).list_notes(None)
    with pytest.raises(ServiceError, match='validation_error'):
        book.execute('create_note', key(), actor_id=book.actor)


def test_atomic_audit_failure(book):
    with book.engine.begin() as c:
        c.exec_driver_sql("CREATE TRIGGER fail_mutation BEFORE INSERT ON audit_events BEGIN SELECT RAISE(ABORT,'injected'); END")
    with pytest.raises(IntegrityError):
        book.execute('create_note', key())
    with book.engine.connect() as c:
        for table in ('notes', 'note_revisions', 'mutation_receipts'):
            assert c.exec_driver_sql(f'SELECT count(*) FROM {table}').scalar() == 0


def test_project_rename_conflict_and_input_normalization(book):
    project = book.list_projects()[0]
    book.execute('rename_project', key(), project_id=project['id'], expected_version=1, name='Capture')
    note = book.execute('create_note', key(), title=' ', body_markdown='a\r\nb')
    assert note['project_id'] == project['id']
    assert book.get_note(note['id'])['title'] == 'Untitled'
    assert book.get_note(note['id'])['body_markdown'] == 'a\nb'
    with pytest.raises(ServiceError, match='version_conflict'):
        book.execute('rename_project', key(), project_id=project['id'], expected_version=1, name='Stale')
