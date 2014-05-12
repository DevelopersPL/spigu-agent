import subprocess

def get_subvolume_id(path):
    volume = '/'
    subvolume_data = dict()
    cmd = ['btrfs',  'subvolume', 'list', volume]
    for line in subprocess.check_output(cmd).splitlines():
        args = line.strip().split(' ')
        subvolume_data[volume + args[-1]] = int(args[1])

    return subvolume_data[path]

