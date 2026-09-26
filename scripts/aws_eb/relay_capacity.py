#!/usr/bin/env python3
"""Reconcile only the existing site's reviewed TURN ingress through CloudFormation."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from render_turn import RELAY_MIN_PORT, RELAY_MAX_PORT

STACK = 'retro-coop-website-foundation'
REGION = 'us-east-1'


def aws(*args):
    result = subprocess.run(['aws', *args, '--region', REGION, '--output', 'json'],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout or '{}')


def validate_changes(changes):
    if len(changes) != 1:
        raise ValueError('Expected only the existing TURN security group to change')
    resource = changes[0].get('ResourceChange', {})
    if (resource.get('LogicalResourceId') != 'AppSecurityGroup'
            or resource.get('ResourceType') != 'AWS::EC2::SecurityGroup'
            or resource.get('Action') != 'Modify' or resource.get('Replacement') != 'False'):
        raise ValueError('Refusing unrelated infrastructure changes or replacement')
    details = resource.get('Details', [])
    if not details or any(detail.get('Target', {}).get('Attribute') != 'Properties'
                          or detail.get('Target', {}).get('Name') != 'SecurityGroupIngress'
                          or detail.get('Target', {}).get('RequiresRecreation') != 'Never'
                          for detail in details):
        raise ValueError('Only an in-place ingress change is permitted')


def verify_ingress(group, max_port=RELAY_MAX_PORT):
    actual = set()
    for rule in group['IpPermissions']:
        if rule.get('Ipv6Ranges') or rule.get('UserIdGroupPairs') or rule.get('PrefixListIds'):
            raise ValueError('Unexpected non-IPv4 ingress')
        for source in rule.get('IpRanges', []):
            actual.add((rule['IpProtocol'], rule.get('FromPort'), rule.get('ToPort'), source['CidrIp']))
    expected = {('tcp', 80, 80, '0.0.0.0/0'), ('tcp', 443, 443, '0.0.0.0/0'),
                ('udp', 3478, 3478, '0.0.0.0/0'),
                ('udp', RELAY_MIN_PORT, max_port, '0.0.0.0/0')}
    if actual != expected:
        raise ValueError('Live ingress does not match the reviewed web and TURN ports')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply the narrowly validated existing-stack change')
    args = parser.parse_args()
    stack = aws('cloudformation', 'describe-stacks', '--stack-name', STACK)['Stacks'][0]
    if stack['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'):
        raise ValueError('Existing foundation is not ready for an update')
    group_id = next(output['OutputValue'] for output in stack['Outputs']
                    if output['OutputKey'] == 'AppSecurityGroupId')
    live_group = aws('ec2', 'describe-security-groups', '--group-ids', group_id)['SecurityGroups'][0]
    try:
        verify_ingress(live_group)
    except ValueError:
        # Migrate only the known prior profile, never reconcile unrelated drift.
        verify_ingress(live_group, max_port=49175)
    else:
        print('Live web/TURN ingress already matches the reviewed limits.')
        return
    template = Path(__file__).resolve().parents[2] / 'deploy/aws-eb/foundation.yaml'
    name = 'five-slot-relay-' + str(time.time_ns())
    change = aws('cloudformation', 'create-change-set', '--stack-name', STACK,
                 '--change-set-name', name, '--change-set-type', 'UPDATE',
                 '--template-body', 'file://' + str(template), '--capabilities', 'CAPABILITY_NAMED_IAM',
                 '--parameters', json.dumps([{'ParameterKey': item['ParameterKey'], 'UsePreviousValue': True}
                                              for item in stack['Parameters']]))
    change_id = change['Id']
    executed = False
    try:
        deadline = time.monotonic() + 90
        while True:
            result = aws('cloudformation', 'describe-change-set', '--change-set-name', change_id)
            if result['Status'] not in ('CREATE_PENDING', 'CREATE_IN_PROGRESS'):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('TURN ingress change-set preparation timed out')
            time.sleep(2)
        if result['Status'] == 'FAILED':
            reason = result.get('StatusReason', '')
            if "didn't contain changes" not in reason and 'No updates are to be performed' not in reason:
                raise ValueError('CloudFormation could not prepare the TURN ingress update')
        else:
            if result['Status'] != 'CREATE_COMPLETE':
                raise ValueError('Unexpected change-set state')
            validate_changes(result.get('Changes', []))
            if not args.apply:
                print('Validated: only existing TURN ingress would change. Rerun with --apply to execute.')
                return
            aws('cloudformation', 'execute-change-set', '--change-set-name', change_id)
            executed = True
            aws('cloudformation', 'wait', 'stack-update-complete', '--stack-name', STACK)
        group = aws('ec2', 'describe-security-groups', '--group-ids', group_id)['SecurityGroups'][0]
        verify_ingress(group)
        print(f'Live web/TURN ingress verified; relay ports {RELAY_MIN_PORT}–{RELAY_MAX_PORT}.')
    finally:
        if not executed:
            aws('cloudformation', 'delete-change-set', '--change-set-name', change_id)


if __name__ == '__main__':
    main()
