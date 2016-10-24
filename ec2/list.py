import argparse
import boto.ec2

access_key = ''
secret_key = ''

def get_ec2_instances(region):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    if ec2_conn:
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name':'pbft'})
        for reservation in reservations:    
            for ins in reservation.instances:
                if ins.public_dns_name:
                    print ins.public_dns_name.split('.')[0][4:].replace('-','.')

def get_ec2_instances_names(region):
    ec2_conn = boto.ec2.connect_to_region(region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key)
    if ec2_conn:
        reservations = ec2_conn.get_all_reservations(filters={'tag:Name':'pbft'})
        for reservation in reservations:    
            for ins in reservation.instances:
                print ins.instance_id

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

def main():
    regions = ['us-east-1','us-west-1','us-west-2','eu-west-1','sa-east-1',
                'ap-southeast-1','ap-southeast-2','ap-northeast-1', 'eu-central-1']
    parser = argparse.ArgumentParser()
    parser.add_argument('access_key', help='Access Key')
    parser.add_argument('secret_key', help='Secret Key')
    args = parser.parse_args()
    global access_key
    global secret_key
    access_key = args.access_key
    secret_key = args.secret_key
    
    for region in regions:
        get_ec2_instances(region)

if  __name__ =='__main__':main()