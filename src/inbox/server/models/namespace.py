""" Namespace-specific functions.

All functions in this file should take `namespace_id` as their first
argument and make sure to limit the action based on it!
"""
from sqlalchemy.orm.exc import NoResultFound

from .tables import Thread, FolderItem

from inbox.util.file import Lock

def _db_write_lockfile_name(account_id):
    return "/var/lock/inbox_datastore/{0}.lock".format(account_id)

def db_write_lock(namespace_id):
    """ Protect updating this namespace's Inbox datastore data.

    Note that you should also use this to wrap any code that _figures
    out_ what to update the datastore with, because outside the lock
    you can't guarantee no one is updating the data behind your back.
    """
    return Lock(_db_write_lockfile_name(namespace_id), block=True)

def threads_for_folder(namespace_id, session, folder_name):
    """ NOTE: Does not work for shared folders. """
    return session.query(Thread).join(FolderItem).filter(
            Thread.namespace_id==namespace_id,
            FolderItem.folder_name==folder_name)

def archive_thread(namespace_id, session, thread_id):
    """ Archive thread in the local datastore (*not* the account backend).

    (Removes it from the 'inbox' and puts it in the 'archive'.)

    Idempotent.
    """
    with db_write_lock(namespace_id):
        try:
            inbox_item = session.query(FolderItem).join(Thread).filter(
                    Thread.namespace_id==namespace_id,
                    FolderItem.thread_id==thread_id,
                    FolderItem.folder_name=='inbox').one()
            session.delete(inbox_item)
        except NoResultFound:
            pass
        try:
            archive_item = session.query(FolderItem).join(Thread).filter(
                    Thread.namespace_id==namespace_id,
                    FolderItem.thread_id==thread_id,
                    FolderItem.folder_name=='archive').one()
        except NoResultFound:
            # TODO: throw a better error in the case that thread_id is invalid
            # (right now it's just going to throw some stupid inconsistency
            # error generated by the foreign key constraint)
            archive_item = FolderItem(thread_id=thread_id,
                    folder_name='archive')
            session.add(archive_item)
        session.commit()

# NOTE: move/copy/delete are not idempotent, but archive is. This could be
# confusing. How can we make it better?

def move_thread(namespace_id, session, thread_id, from_folder, to_folder):
    """ Move thread in the local datastore (*not* the account backend). """
    with db_write_lock(namespace_id):
        listings = {item.folder_name: item for item in \
                session.query(FolderItem).join(Thread).filter(
                Thread.namespace_id==namespace_id,
                FolderItem.thread_id==thread_id,
                FolderItem.folder_name.in_([from_folder, to_folder])).all()}
        if to_folder not in listings:
            listings[from_folder].folder_name = to_folder
            session.commit()

def copy_thread(namespace_id, session, thread_id, from_folder, to_folder):
    """ Copy thread in the local datastore (*not* the account backend). """
    with db_write_lock(namespace_id):
        existing = session.query(FolderItem).join(Thread).filter(
                Thread.namespace_id==namespace_id,
                FolderItem.thread_id==thread_id,
                FolderItem.folder_name==from_folder).one()
        new = FolderItem(thread=existing.thread, folder_name=to_folder)
        session.add(new)
        session.commit()

def delete_thread(namespace_id, session, thread_id, folder_name):
    """ Delete thread in the local datastore (*not* the account backend). """
    with db_write_lock(namespace_id):
        item = session.query(FolderItem).join(Thread).filter(
                Thread.namespace_id==namespace_id,
                FolderItem.thread_id==thread_id,
                FolderItem.folder_name==folder_name).one()
        session.delete(item)
        session.commit()
