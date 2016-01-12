#!/usr/bin/env python
"""
My appologies for the hack job...
"""

import os
from boto.ec2.connection import EC2Connection
from boto.vpc import VPCConnection

try:
    import json
except ImportError:
    import simplejson as json


class Ec2Inventory(object):
    def _empty_inventory(self):
        return {"_meta" : {"hostvars" : {}}}

    def __init__(self):
        ''' Main execution path '''

        # Inventory grouped by instance IDs, tags, security groups, regions,
        # and availability zones
        self.inventory = self._empty_inventory()

        # Index of hostname (address) to instance ID
        self.index = {}

        self.config = {}
        self.config['exclude_windows'] = True
        self.config['states'] = "running"

        # Index of VPC's with options
        self.vpcs = {}
        self.instances = {}
        self._get_vpc_details()
        self._get_all_instances()
        self._setup_inventory()


    def _get_vpc_details(self):
        """
        Create dictonary with VPC's info and tags
        """
        # Connect to AWS for VPC
        vpc_conn = VPCConnection()

        # Grab VPCs
        vpcs_data = vpc_conn.get_all_vpcs()

        for vpc in vpcs_data:
            tags = {}
            tags['state'] = vpc.state
            tags['cidr'] = vpc.cidr_block
            for key, value in vpc.tags.items():
                tags[key.lower()] = value.lower()

        # assing vpcs to class vpcs
        self.vpcs = {vpc.id: tags}


    def _get_all_instances(self):
        """
        Create dictonary of EC2 hosts setting hostvars and groups
        """
        # Connect to AWS for EC2
        conn = EC2Connection()

        # Grab list of EC2 Instances
        instances = conn.get_only_instances(max_results=10)

        myinstances = {}

        for inst in instances:
            if inst.state != 'running':
                continue

            tags = {}
            tags['ec2_state'] = inst.state
            tags['ec2_type'] = inst.instance_type
            tags['ec2_key_name'] = inst.key_name
            tags['ec2_az'] = inst.placement
            tags['ec2_vpc'] = inst.vpc_id
            tags['ec2_subnet'] = inst.subnet_id
            tags['ec2_root_device_type'] = inst.root_device_type
            tags['ec2_root_device_name'] = inst.root_device_name

            if inst.platform == 'windows':
                tags['ec2_platform'] = inst.platform
            else:
                tags['ec2_platform'] = 'linux'

            try:
                tags['ec2_ip'] = inst.private_ip_address
            except:
                tags['ec2_ip'] = inst.ip_address

            # Make sure I have a role
            tags['ec2_role'] = 'unset'

            # Loop through tags
            for k, v in inst.tags.items():
                if k == 'role':
                    tags['ec2_role'] = v
                tags['ec2_'+k.lower()] = v.lower()

            myinstances[inst.id] = tags

        self.instances = myinstances

    def _setup_inventory(self):
        from pprint import pprint
        # this has gotten messy and needs refactoring
        for instance, data in self.instances.items():

            if data['ec2_vpc'] != None:
                data['bastion'] = self.vpcs[data['ec2_vpc']]['bastion']
                data['ansible_ssh_host'] = data['ec2_name'] + "." + self.vpcs[data['ec2_vpc']]['domain']
            else:
                data['ansible_ssh_host'] = data['ec2_name'] + '.' + 'example.com'

            if ',' in data['ec2_role']:
                roles = data['ec2_role'].split(',')
                for role in roles:
                    self.inventory.setdefault(role, [])
                    self.inventory[role].append(data['ec2_name'])
            else:
                self.inventory.setdefault(data['ec2_role'], [])
                self.inventory[data['ec2_role']].append(data['ec2_name'])

            for k, v in data.items():
                if k != 'ec2_name':
                    data[k] = v
            self.inventory['_meta']['hostvars'][data['ec2_name']] = data

    def display_inventory(self):
        print json.dumps(self.inventory, sort_keys=True, indent=2)


def main():
    inventory = Ec2Inventory()
    inventory.display_inventory()

if __name__ == '__main__':
    main()
