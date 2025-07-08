import time

from da.listen.keyboard_watcher import KeyboardWatcher


def test():
    watcher = KeyboardWatcher()
    watcher.start()
    time.sleep(5)
    watcher.stop()


if __name__ == '__main__':
    test()
