#!/usr/bin/env python


import os
from src.app import Boobot



bot_token = ''
admin_id = ''
engine_uri = ''
oc_host = ''
mtproto_proxy = ''

bb = Boobot(bot_token=bot_token, admin_id=admin_id, engine_uri=engine_uri, oc_host=oc_host, mtproto_proxy=mtproto_proxy)
bb.run()

