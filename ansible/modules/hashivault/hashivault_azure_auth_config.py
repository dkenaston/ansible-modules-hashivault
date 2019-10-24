#!/usr/bin/env python
from ansible.module_utils.hashivault import hashivault_argspec
from ansible.module_utils.hashivault import hashivault_auth_client
from ansible.module_utils.hashivault import hashivault_init
from ansible.module_utils.hashivault import hashiwrapper
import json, sys

ANSIBLE_METADATA = {'status': ['stableinterface'], 'supported_by': 'community', 'version': '1.1'}
DOCUMENTATION = '''
---
module: hashivault_azure_auth_config
version_added: "3.17.7"
short_description: Hashicorp Vault azure auth config
description:
    - Module to configure an azure auth mount
options:
    url:
        description:
            - url for vault
        default: to environment variable VAULT_ADDR
    ca_cert:
        description:
            - "path to a PEM-encoded CA cert file to use to verify the Vault server TLS certificate"
        default: to environment variable VAULT_CACERT
    ca_path:
        description:
            - "path to a directory of PEM-encoded CA cert files to verify the Vault server TLS certificate : if ca_cert
             is specified, its value will take precedence"
        default: to environment variable VAULT_CAPATH
    client_cert:
        description:
            - "path to a PEM-encoded client certificate for TLS authentication to the Vault server"
        default: to environment variable VAULT_CLIENT_CERT
    client_key:
        description:
            - "path to an unencrypted PEM-encoded private key matching the client certificate"
        default: to environment variable VAULT_CLIENT_KEY
    verify:
        description:
            - "if set, do not verify presented TLS certificate before communicating with Vault server : setting this
             variable is not recommended except during testing"
        default: to environment variable VAULT_SKIP_VERIFY
    authtype:
        description:
            - "authentication type to use: token, userpass, github, ldap, approle"
        default: token
    token:
        description:
            - token for vault
        default: to environment variable VAULT_TOKEN
    username:
        description:
            - username to login to vault.
        default: to environment variable VAULT_USER
    password:
        description:
            - password to login to vault.
        default: to environment variable VAULT_PASSWORD
    mount_point:
        description:
            - name of the secret engine mount name.
        default: azure
    tenant_id:
        description:
            - azure SPN tenant id
    client_id:
        description:
            - azure SPN client id
    client_secret:
        description:
            - azure SPN client secret
    config_file:
        description:
            - alternate way to pass SPN vars. must be json object
    environment:
        description:
            - azure environment. default is likely OK
        default: AzurePublicCloud
    resource:
        description:
            - the azure AD resource the auth method accesses. default is likely OK
        default: https://management.azure.com
'''
EXAMPLES = '''
---
- hosts: localhost
  tasks:
    - hashivault_azure_auth_config:
        tenant_id: 5689-1234
        client_id: 1012-1234
        client_secret: 1314-1234

    - hashivault_azure_auth_config:
        config_file: /home/drewbuntu/azure-auth-config.json
'''


def main():
    argspec = hashivault_argspec()
    argspec['mount_point'] = dict(required=False, type='str', default='azure')
    argspec['tenant_id'] = dict(required=False, type='str')
    argspec['client_id'] = dict(required=False, type='str')
    argspec['client_secret'] = dict(required=False, type='str')
    argspec['environment'] = dict(required=False, type='str', default='AzurePublicCloud')
    argspec['resource'] = dict(required=False, type='str', default='https://management.azure.com')
    argspec['config_file'] = dict(required=False, type='str', default=None)
    supports_check_mode=True
    required_together=[['client_id', 'client_secret', 'tenant_id']]

    module = hashivault_init(argspec, supports_check_mode, required_together)
    result = hashivault_azure_auth_config(module)
    if result.get('failed'):
        module.fail_json(**result)
    else:
        module.exit_json(**result)


@hashiwrapper
def hashivault_azure_auth_config(module):
    params = module.params
    client = hashivault_auth_client(params)
    changed = False
    config_file = params.get('config_file')
    mount_point = params.get('mount_point')
    desired_state = dict()
    current_state = dict()
    enabled_methods = list()

    # do not want a trailing slash in mount_point
    if mount_point[-1]:
        mount_point = mount_point.strip('/')

    # if config_file is set, set sub_id, ten_id, client_id, client_secret from file
    # else set from passed args
    if config_file:
        desired_state = json.loads(open(params.get('config_file'), 'r').read())
        if 'resource' not in desired_state:
            desired_state['resource'] = params.get('resource')
        if 'environment' not in desired_state:
            desired_state['environment'] = params.get('environment')
    else:
        desired_state['tenant_id'] = params.get('tenant_id')
        desired_state['client_id'] = params.get('client_id')
        desired_state['client_secret'] = params.get('client_secret')
        desired_state['resource'] = params.get('resource')
        desired_state['environment'] = params.get('environment')

    # check if mount exists
    # if errors but check mode is enabled then pass as "changed"
    # while this is technically incorrect, its more likely helpful than hurtful
    try:
        enabled_methods = client.sys.list_auth_methods()['data'].keys()
        if (mount_point + "/") not in enabled_methods:
            return {'failed': True, 'msg': 'auth mount is not enabled', 'rc': 1}
    except:
        if module.check_mode:
            changed = True
        else:
            return {'failed': True, 'msg': 'auth mount is not enabled or namespace does not exist', 'rc': 1}

    try:
        current_state = client.auth.azure.read_config()
    except:
        changed = True

    # check if current config matches desired config values, if they dont match, set changed true
    for k, v in current_state.items():
        if v != desired_state[k]:
            changed = True

    # if configs dont match and checkmode is off, complete the change
    if changed == True and not module.check_mode:
        result = client.auth.azure.configure(mount_point=mount_point, **desired_state)

    return {'changed': changed}


if __name__ == '__main__':
    main()
