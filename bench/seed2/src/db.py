_USERS = {}


def reset():
    _USERS.clear()


def save_user(user):
    _USERS[user.email] = user
    return user


def get_user(email):
    try:
        return _USERS[email]
    except:
        return None
