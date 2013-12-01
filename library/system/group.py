import grp
import library.basic as basic

def group_exists(group):
    try:
        if group.isdigit():
            if grp.getgrgid(group):
                return True
        else:
            if grp.getgrnam(group):
                return True
    except KeyError:
        return False

def group_delete(group):
    cmd = ['/usr/sbin/delgroup']
    cmd.append(group)

    basic.run_command(cmd)

def group_info(group):
    if not group_exists(group):
        return False
    if group.isdigit():
        return list(grp.getgrgid(group))
    else:
        return list(grp.getgrnam(group))