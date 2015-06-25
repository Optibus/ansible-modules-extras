#!/usr/bin/python

DOCUMENTATION = '''

module: pingdom
short_description: Pause/unpause Pingdom alerts
description:
    - This module will let you pause/unpause Pingdom alerts
version_added: "1.2"
author: 
    - "Dylan Silva (@thaumos)"
    - "Justin Johns"
requirements:
    - "This pingdom python library: https://github.com/mbabineau/pingdom-python"
options:
    state:
        description:
            - Define whether or not the check should be running or paused.
        required: true
        default: null
        choices: [ "running", "paused" ]
        aliases: []
    checkid:
        description:
            - Pingdom ID of the check.
        required: true
        default: null
        choices: []
        aliases: []
    uid:
        description:
            - Pingdom user ID.
        required: true
        default: null
        choices: []
        aliases: []
    passwd:
        description:
            - Pingdom user password.
        required: true
        default: null
        choices: []
        aliases: []
    key:
        description:
            - Pingdom API key.
        required: true
        default: null
        choices: []
        aliases: []
    checktype:
        description:
            - Check type. See https://www.pingdom.com/resources/api#MethodCreate+New+Check
        choices: [ "http" ]
        aliases: []
        default: null
        required: false
    host:
        description:
            - Target host
        choices: []
        aliases: []
        default: null
        required: false
    alert_policy:
        description:
            - Alert policy ID
        choices: []
        aliases: []
        default: null
        required: false
    url:
        description:
            - URL on target host (e.g. /)
        choices: []
        aliases: []
        default: null
        required: false
    encryption:
        description:
            - Use HTTPS
        choices: ['yes', 'no']
        aliases: []
        default: null
        required: false
    port:
        description:
            - If you set HTTPS, set this to the right port as well (typically 443)
        choices: []
        aliases: []
        default: null
        required: false
    resolution:
        description:
            - Check reolution (minutes)
        choices: [1, 5, 15, 30, 60)
        default: null
        required: false
        aliases: []


notes:
    - This module does not yet have support to add/remove checks.
'''

EXAMPLES = '''
# Pause the check with the ID of 12345.
- pingdom: uid=example@example.com
           passwd=password123
           key=apipassword123
           checkid=12345
           state=paused

# Unpause the check with the ID of 12345.
- pingdom: uid=example@example.com
           passwd=password123
           key=apipassword123
           checkid=12345
           state=running

# Create new HTTP check
- pingdom: uid=example@example.com
           passwd=password123
           key=apipassword123
           checkname="my website"
           host="www.example.com"
           checktype=http
           alert_policy=12345
           url=/

'''

try:
    import pingdom
    HAS_PINGDOM = True
except:
    HAS_PINGDOM = False


class Pingdom(object):

    def __init__(self, uid, passwd, key, module):
        self.uid = uid
        self.passwd = passwd
        self.key = key
        self.conn = pingdom.PingdomConnection(uid, passwd, key)
        self.module = module

    def modify_check(self, checkid, paused, **kwargs):
        before_change = self.conn.get_check(checkid)
        changed = (before_change.status == 'paused') != paused
        # TODO: track the changed state of all kwargs
        self.conn.modify_check(checkid, paused=paused, **kwargs)
        after_change = self.conn.get_check(checkid)
        return (after_change, changed)

    def delete_check(self, checkid):
        self.conn.delete_check(checkid)

    def find_by_name(self, checkname):
        checks = self.conn.get_all_checks([checkname])
        if len(checks) == 0:
            return None
        return checks[0]

    def find_by_id(self, checkid):
        try:
            return self.conn.get_check(checkid)
        except:
            self.module.fail_json(msg="Cannot find check (id: %s)" % checkid)

    def create_check(self, name, checktype, host, **kwargs):
        check = self.conn.create_check(name, host, checktype, **kwargs)
        check = self.find_by_id(check.id)
        return check

def main():

    module = AnsibleModule(
        argument_spec=dict(
        state=dict(required=True, choices=['running', 'paused', 'started', 'stopped', 'absent']),
        checkid=dict(),
        checkname=dict(),
        checktype=dict(choices=['http']),
        host=dict(),
        encryption=dict(choices=BOOLEANS),
        port=dict(),
        alert_policy=dict(),
        url=dict(),
        resolution=dict(),
        uid=dict(required=True),
        passwd=dict(required=True),
        key=dict(required=True)
        )
    )

    if not HAS_PINGDOM:
        module.fail_json(msg="Missing required pingdom module (check docs)")


    uid = module.params['uid']
    passwd = module.params['passwd']
    key = module.params['key']
    desired_state = module.params['state']
    p = Pingdom(uid, passwd, key, module)

    url = module.params["url"]
    checktype = module.params["checktype"]
    checkname = module.params['checkname']
    checkid = module.params['checkid']
    host = module.params["host"]
    encryption = module.params["encryption"]
    if encryption is not None:
        encryption = module.boolean(encryption)
    resolution = module.params["resolution"]
    port = module.params["port"]
    alert_policy = module.params["alert_policy"]

    if checkid is None and checkname is None:
        module.fail_json(msg="Either checkid or checkname must be specified")

    if checkid is not None:
        check = p.find_by_id(checkid)
    else:
        check = p.find_by_name(checkname)

    current_state = 'absent'
    if check is not None:
        current_state = "paused" if check.status == "paused" else "running"

    changed = False

    try:
        if current_state == 'absent':
            if desired_state in ["running", "started", "paused"]:
                if host is None:
                    module.fail_json(msg="host must be specified when creating new checks")
                if checktype is None:
                    module.fail_json(msg="checktype must be specified when creating new checks")
                check = p.create_check(checkname, 
                        checktype, 
                        host, 
                        url=url, 
                        alert_policy=alert_policy,
                        encryption=encryption,
                        port=port,
                        resolution=resolution,
                        paused=(desired_state=="paused"))
                changed = True
            elif desired_state == 'absent':
                module.exit_json(changed=False)
        else:
            if desired_state == 'absent':
                p.delete_check(check.id)
                changed = True
            else:
                paused = desired_state in ["paused", "stopped"]
                (check, changed) = p.modify_check(check.id, paused=paused, alert_policy=alert_policy, host=host,
                        url=url, encryption=encryption, port=port, resolution=resolution)
    except Exception, e:
        module.fail_json(msg=str(e))

    module.exit_json(checkid=check.id, name=check.name, status=check.status, changed=changed)

# import module snippets
from ansible.module_utils.basic import *
main()
