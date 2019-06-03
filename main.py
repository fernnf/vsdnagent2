import sys
import logging
import coloredlogs
from ryu.cmd import manager

logger =  logging.getLogger("main_vsdnagent")
def main():
    sys.argv.append('--ofp-tcp-listen-port')
    sys.argv.append('6653')
    sys.argv.append('vsdnagent')
    sys.argv.append('--verbose')
    # sys.argv.append('--enable-debugger')
    manager.main()


if __name__ == '__main__':
    main()
    coloredlogs.install(logger=logger)
    logger.info("Starting vSDNAgent")
