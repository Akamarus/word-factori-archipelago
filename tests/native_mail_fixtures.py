def mail_manifest():
    return dict(version=2, session='a'*32, renderer='b'*32, revision=0, heartbeat=0)


def mail_snapshot():
    from word_factori.progress_protocol import unavailable_fields
    return dict(version=2, session='a'*32, renderer='b'*32, revision=0,
                room='room-A', contract='contract-A', connection='connected',
                items=[], chat=[], words=[], notifications=[], unread=0,
                acks=[], history=dict(items=None, chat=None), **unavailable_fields())


def mail_request(sequence=1, action='submit-text', text='hello'):
    return dict(version=2, session='a'*32, renderer='b'*32, room='room-A',
                sequence=sequence, action=action, payload={'text': text})


def mail_item(key='delivery-1'):
    return dict(key=key, direction='received', item='Bender Access',
                player='Player 2', location='Complete C', historical=False, unread=True)
