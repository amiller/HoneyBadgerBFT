import argparse
import boto.ec2
import time
if not boto.config.has_section('ec2'):
    boto.config.add_section('ec2')
    boto.config.setbool('ec2','use-sigv4',True)

secgroups = {
    'us-east-1':'sg-6c4dfe0a',
    'us-west-1':'sg-7b34651e',
    'us-west-2':'sg-8f067ceb',
    'eu-west-1':'sg-368c3152',
    'sa-east-1':'sg-2a1f744f',
    'ap-southeast-1':'sg-2d491c48',
#    'ap-southeast-2':'sg-d58dd4b0',
    'ap-northeast-1':'sg-499fb02c',
    'eu-central-1':'sg-2bfe9342'}
regions = sorted(secgroups.keys())[::-1]

NameFilter = 'Badger'
    
def getAddrFromEC2Summary(s):
    return [
            x.split('ec2.')[-1] for x in s.replace(
                '.compute.amazonaws.com', ''
                ).replace(
                    '.us-west-1', ''    # Later we need to add more such lines
                    ).replace(
                        '-', '.'
                        ).strip().split('\n')]

def get_ec2_instances_ip(region):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    if ec2_conn:
        result = []
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name': NameFilter})
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
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name': NameFilter})
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
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name': NameFilter})
        for reservation in reservations:    
            for ins in reservation.instances:
                idList.append(ins.id)
    ec2_conn.stop_instances(instance_ids=idList)

def terminate_all_instances(region):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    idList = []
    if ec2_conn:
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name': NameFilter})
        for reservation in reservations:    
            for ins in reservation.instances:
                idList.append(ins.id)
    ec2_conn.terminate_instances(instance_ids=idList)

def launch_new_instances(region, number):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    dev_sda1 = boto.ec2.blockdevicemapping.EBSBlockDeviceType(delete_on_termination=True)
    dev_sda1.size = 8 # size in Gigabytes
    dev_sda1.delete_on_terminate = True
    bdm = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    bdm['/dev/sda1'] = dev_sda1
    img = ec2_conn.get_all_images(filters={'name':'ubuntu/images/hvm-ssd/ubuntu-trusty-14.04-amd64-server-20150325'})[0].id
    reservation = ec2_conn.run_instances(image_id=img, #'ami-df6a8b9b', 
                                 min_count=number,
                                 max_count=number,
                                 key_name='amiller-mc2ec2', 
                                 instance_type='t2.medium',
                                 security_group_ids = [secgroups[region], ],
                                 
                                 #subnet_id = 'vpc-037ab266',
                                 block_device_map = bdm)
    for instance in reservation.instances:
        instance.add_tag("Name", NameFilter)
    return reservation


def start_all_instances(region):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    idList = []
    if ec2_conn:
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name': NameFilter})
        for reservation in reservations:    
            for ins in reservation.instances:
                idList.append(ins.instance_id)
    ec2_conn.start_instances(instance_ids=idList)


def ipAll():
    result = []
    for region in regions:
        result += get_ec2_instances_ip(region) or []
    open('hosts','w').write('\n'.join(result))
    callFabFromIPList(result, 'removeHosts')
    callFabFromIPList(result, 'writeHosts')
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

from subprocess import check_output, Popen, call, PIPE, STDOUT
import platform


def callFabFromIPList(l, work):
    if platform.system() == 'Darwin':
        print Popen(['fab', '-i', '~/.ssh/amiller-mc2ec2.pem',
            '-u', 'ubuntu', '-H', ','.join(l), # We rule out the client
            work])
    else:
        call('fab -i ~/.ssh/amiller-mc2ec2.pem -u ubuntu -P -H %s %s' % (','.join(l), work), shell=True)


def callStartProtocolAndMonitorOutput(N, t, l, work='runProtocol'):
    starting_time = time.time()
    if platform.system() == 'Darwin':
        popen = Popen(['fab', '-i', '~/.ssh/amiller-mc2ec2.pem',
            '-u', 'ubuntu', '-H', ','.join(l),
            work], stdout=PIPE, stderr=STDOUT, close_fds=True)
    else:
        popen = Popen('fab -i ~/.ssh/amiller-mc2ec2.pem -u ubuntu -P -H %s %s' % (','.join(l), work), shell=True, stdout=PIPE, stderr=PIPE)
    lines_iterator = iter(popen.stdout.readline, b"")
    counter = 0
    for line in lines_iterator:
        if 'synced transactions set' in line:
            counter += 1
        if counter >= N - t:
            break
        print line # yield line
    ending_time = time.time()
    print 'Latency from client scope:', ending_time - starting_time



def callFab(s, work):  # Depracated
    # open('hosts','w').write('\n'.join(getAddrFromEC2Summary(s)))
    print Popen(['fab', '-i', '~/.ssh/amiller-mc2ec2.pem', 
            '-u', 'ubuntu', '-H', ','.join(getAddrFromEC2Summary(s)),
            work])

if  __name__ =='__main__':
  try: __IPYTHON__
  except NameError:
    parser = argparse.ArgumentParser()
    parser.add_argument('access_key', help='Access Key');
    parser.add_argument('secret_key', help='Secret Key');
    args = parser.parse_args()
    access_key = args.access_key
    secret_key = args.secret_key

    import IPython
    IPython.embed()

