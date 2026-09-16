SESSION_TTL = 300


def new_session(user_email, now):
    return {"user": user_email, "created_at": now, "last_seen": now}


def touch(session, now):
    session["last_seen"] = now
    return session


def is_session_valid(session, now):
    return now - session["created_at"] < SESSION_TTL
