import argparse
import boto.ec2

regions = ['us-east-1','us-west-1','us-west-2','eu-west-1','sa-east-1',
    'ap-southeast-1','ap-southeast-2','ap-northeast-1'] ##, 'eu-central-1b']
    
def getAddrFromEC2Summary(s):
    return [
            x.split('ec2.')[-1] for x in s.replace(
                '.compute.amazonaws.com', ''
                ).replace(
                    '.us-west-1', ''    # Later we need to add more such lines
                    ).replace(
                        '-', '.'
                        ).strip().split('\n')]

access_key = ''
secret_key = ''

def get_ec2_instances_ip(region):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    if ec2_conn:
        result = []
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name':'pbft'})
        for reservation in reservations:    
            for ins in reservation.instances:
                if ins.public_dns_name: 
                # ec2-54-153-121-229.us-west-1.compute.amazonaws.com
                    currentIP = ins.public_dns_name.split('.')[0][4:].replace('-','.')
                    result.append(currentIP)
                    print currentIP
        return result
    else:
        print 'Region failed', region
        return None

def get_ec2_instances_id(region):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    if ec2_conn:
        result = []
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name':'pbft'})
        for reservation in reservations:    
            for ins in reservation.instances:
                print ins.id
                result.append(ins.id)
        return result
    else:
        print 'Region failed', region
        return None

def stop_all_instances(region):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    idList = []
    if ec2_conn:
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name':'pbft'})
        for reservation in reservations:    
            for ins in reservation.instances:
                idList.append(ins.instance_id)
    ec2_conn.stop_instances(instance_ids=idList)

def launch_new_instances(region, number):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    dev_sda1 = boto.ec2.blockdevicemapping.EBSBlockDeviceType()
    dev_sda1.size = 8 # size in Gigabytes
    bdm = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    bdm['/dev/sda1'] = dev_sda1
    reservation = ec2_conn.run_instances(image_id='ami-df6a8b9b', 
                                 min_count=number,
                                 max_count=number,
                                 key_name='amiller-mc2ec2', 
                                 instance_type='t2.micro',
                                 security_groups = ['sg-7b34651e', ],
                                 subnet_id = 'vpc-037ab266'
                                 block_device_mappings = [bdm])
    return reservation

def start_all_instances(region):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    idList = []
    if ec2_conn:
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name':'pbft'})
        for reservation in reservations:    
            for ins in reservation.instances:
                idList.append(ins.instance_id)
    ec2_conn.start_instances(instance_ids=idList)

def ipAll():
    result = []
    for region in regions:
        result += get_ec2_instances_ip(region) or []
    open('hosts','w').write('\n'.join(result))
    callFabFromIPList(result, 'removeHosts', iC=True)
    callFabFromIPList(result, 'writeHosts', iC=True)
    return result

def getIP():
    return [l for l in open('hosts', 'r').read().split('\n') if l]

def idAll():
    result = []
    for region in regions:
        result += get_ec2_instances_id(region) or []
    return result

def startAll():
    for region in regions:
        start_all_instances(region)

def stopAll():
    for region in regions:
        stop_all_instances(region)

from subprocess import check_output, Popen

def callFabFromIPList(l, work, iC=False):
    # open('hosts','w').write('\n'.join(l))
    if iC:
        print Popen(['fab', '-i', '~/.ssh/amiller-mc2ec2.pem', 
            '-u', 'ubuntu', '-H', ','.join(l), # We rule out the client
            work])
    else:
        print Popen(['fab', '-i', '~/.ssh/amiller-mc2ec2.pem', 
            '-u', 'ubuntu', '-H', ','.join(l[:-1]), # We rule out the client
            work])

def callFabFromIPListREV(l, work, iC=False):  ### This is just for PBFT start the protocol
    # open('hosts','w').write('\n'.join(l))
    if iC:
        print Popen(['fab', '-i', '~/.ssh/amiller-mc2ec2.pem', 
            '-u', 'ubuntu', '-H', ','.join(l[::-1]), # We rule out the client
            work])
    else:
        print Popen(['fab', '-i', '~/.ssh/amiller-mc2ec2.pem', 
            '-u', 'ubuntu', '-H', ','.join(l[::-1][1:]), # We rule out the client
            work])

def callFab(s, work):
    # open('hosts','w').write('\n'.join(getAddrFromEC2Summary(s)))
    print Popen(['fab', '-i', '~/.ssh/amiller-mc2ec2.pem', 
            '-u', 'ubuntu', '-H', ','.join(getAddrFromEC2Summary(s)),
            work])

if  __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('access_key', help='Access Key');
    parser.add_argument('secret_key', help='Secret Key');
    args = parser.parse_args()
    access_key = args.access_key
    secret_key = args.secret_key

    import IPython
    IPython.embed()

