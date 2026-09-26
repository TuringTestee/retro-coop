import copy
import unittest
from unittest.mock import patch
import relay_capacity
from relay_capacity import validate_changes, verify_ingress
from render_turn import RELAY_MIN_PORT, RELAY_MAX_PORT


class RelayMigrationTests(unittest.TestCase):
    def setUp(self):
        self.change = {'ResourceChange': {'LogicalResourceId': 'AppSecurityGroup',
            'ResourceType': 'AWS::EC2::SecurityGroup', 'Action': 'Modify', 'Replacement': 'False',
            'Details': [{'Target': {'Attribute': 'Properties', 'Name': 'SecurityGroupIngress', 'RequiresRecreation': 'Never'}}]}}
        self.group = {'IpPermissions': [{'IpProtocol': protocol, 'FromPort': first, 'ToPort': last,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]} for protocol, first, last in
            [('tcp', 80, 80), ('tcp', 443, 443), ('udp', 3478, 3478),
             ('udp', RELAY_MIN_PORT, RELAY_MAX_PORT)]]}

    def test_only_ingress_update_accepted(self):
        validate_changes([self.change])
        for field, value in [('LogicalResourceId', 'CostGuard'), ('Action', 'Add'),
                             ('Replacement', 'True'), ('ResourceType', 'AWS::EC2::Instance')]:
            change = copy.deepcopy(self.change)
            change['ResourceChange'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_changes([change])
        for changes in [[], [self.change, self.change]]:
            with self.assertRaises(ValueError):
                validate_changes(changes)

    def test_other_properties_and_recreation_rejected(self):
        for detail in [[], [{'Target': {'Attribute': 'Properties', 'Name': 'SecurityGroupEgress', 'RequiresRecreation': 'Never'}}],
                       [{'Target': {'Attribute': 'Properties', 'Name': 'SecurityGroupIngress', 'RequiresRecreation': 'Conditionally'}}]]:
            change = copy.deepcopy(self.change)
            change['ResourceChange']['Details'] = detail
            with self.assertRaises(ValueError):
                validate_changes([change])

    def test_known_old_profile_is_the_only_migration_source(self):
        old = copy.deepcopy(self.group)
        old['IpPermissions'][-1]['ToPort'] = 49175
        verify_ingress(old, max_port=49175)
        old['IpPermissions'].append({'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22,
                                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]})
        with self.assertRaises(ValueError):
            verify_ingress(old, max_port=49175)

    def test_update_executes_only_validated_change_and_verifies_live_ports(self):
        for unsafe in [False, True]:
            old = copy.deepcopy(self.group)
            old['IpPermissions'][-1]['ToPort'] = 49175
            proposed = copy.deepcopy(self.change)
            if unsafe:
                proposed['ResourceChange']['LogicalResourceId'] = 'CostGuard'
            calls = []
            def fake_aws(*args):
                calls.append(args)
                operation = args[1]
                if operation == 'describe-stacks':
                    return {'Stacks': [{'StackStatus': 'UPDATE_COMPLETE',
                        'Outputs': [{'OutputKey': 'AppSecurityGroupId', 'OutputValue': 'sg-existing'}],
                        'Parameters': [{'ParameterKey': 'VpcId', 'ParameterValue': 'vpc-private'}]}]}
                if operation == 'describe-security-groups':
                    applied = any(call[1] == 'execute-change-set' for call in calls)
                    return {'SecurityGroups': [self.group if applied else old]}
                if operation == 'create-change-set':
                    self.assertIn('UsePreviousValue', args[-1])
                    self.assertNotIn('vpc-private', args[-1])
                    return {'Id': 'change-existing-stack'}
                if operation == 'describe-change-set':
                    return {'Status': 'CREATE_COMPLETE', 'Changes': [proposed]}
                return {}
            with self.subTest(unsafe=unsafe), patch.object(relay_capacity, 'aws', fake_aws), patch('sys.argv', ['relay_capacity.py', '--apply']), patch('builtins.print'):
                if unsafe:
                    with self.assertRaises(ValueError): relay_capacity.main()
                else:
                    relay_capacity.main()
            operations = [call[1] for call in calls]
            self.assertEqual('execute-change-set' in operations, not unsafe)
            self.assertEqual('delete-change-set' in operations, unsafe)
            if not unsafe:
                self.assertEqual(operations[-1], 'describe-security-groups')

    def test_exact_live_ports_required(self):
        verify_ingress(self.group)
        for mode in ['old_range', 'ssh', 'ipv6', 'private', 'empty']:
            group = copy.deepcopy(self.group)
            if mode == 'old_range': group['IpPermissions'][-1]['ToPort'] = 49175
            if mode == 'ssh': group['IpPermissions'].append({'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]})
            if mode == 'ipv6': group['IpPermissions'][0]['Ipv6Ranges'] = [{'CidrIpv6': '::/0'}]
            if mode == 'private': group['IpPermissions'][0]['IpRanges'][0]['CidrIp'] = '10.0.0.0/8'
            if mode == 'empty': group['IpPermissions'].pop()
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify_ingress(group)


if __name__ == '__main__':
    unittest.main()
