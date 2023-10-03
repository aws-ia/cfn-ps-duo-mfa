import os
import boto3
import json
import time
from enum import Enum

class RadiusStatus(Enum):
    Creating = 1
    Completed = 2
    Failed = 3
    NotConfigured = 4

# Constants
RADIUS_TIMEOUT = 10
RADIUS_RETRIES = 3
RADIUS_AUTHENTICATION_PROTOCOL = 'PAP'

ds_client = boto3.client('ds')
ec2_client = boto3.client('ec2')
secretsmanager_client = boto3.client('secretsmanager')


#========================================
# Function handler
#========================================
def lambda_handler(event, context):

    print(json.dumps(event))

    directory_service_id = os.environ['directory_service_id']
    radius_proxy_server_count = int(os.environ['radius_proxy_server_count'])

    print('Directory Service Id: {}'.format(directory_service_id))

    # Disable RADIUS for this directory.
    if 'RequestType' in event and 'Delete' in event['RequestType']:
        response = ds_client.disable_radius(DirectoryId = directory_service_id)

    else:

        # Get the number of running and configured RADIUS proxy servers.
        instance_private_ip_addresses = get_instance_private_ip_addresses(directory_service_id)

        # Ensure that the designated number of instances is up.
        if len(instance_private_ip_addresses) < radius_proxy_server_count:
            print('Found addresses: {}, but two are required.'.format(json.dumps(instance_private_ip_addresses)))
            return {"Status":"Failed", "Reason":"Address count of {} is not two".format(len(instance_private_ip_addresses))}

        # Enable RADIUS for the given directory ID.
        else:
            print('Found addresses: {}.'.format(json.dumps(instance_private_ip_addresses)))
            enable_radius(directory_service_id, instance_private_ip_addresses)


#========================================
# function: enable_radius
#========================================
def enable_radius(directory_service_id, instance_private_ip_addresses):

    radius_port_number = int(os.environ['radius_proxy_port_number'])
    radius_shared_secret = get_radius_shared_secret(os.environ['radius_shared_secret_arn'])

    radius_settings = {
        "RadiusServers": instance_private_ip_addresses,
        "RadiusPort": radius_port_number,
        "RadiusTimeout": RADIUS_TIMEOUT,
        "RadiusRetries": RADIUS_RETRIES,
        "SharedSecret": radius_shared_secret,
        "AuthenticationProtocol": RADIUS_AUTHENTICATION_PROTOCOL,
        "DisplayLabel": "Duo MFA"
    }

    # Determine whether RADIUS has been configured.
    radius_status = get_directory_service_radius_status(directory_service_id)
    print('Current RADIUS status: {}.'.format(radius_status))

    # Enable RADIUS.
    if radius_status in [RadiusStatus.NotConfigured, RadiusStatus.Failed]:
        # Enable the RADIUS settings for this directory.
        print('Enabling RADIUS configuration...')
        response = ds_client.enable_radius(
            DirectoryId = directory_service_id,
            RadiusSettings = radius_settings
        )

    # Update RADIUS.
    elif radius_status == RadiusStatus.Completed:
        # Update the RADIUS settings for this directory.
        print('Updating RADIUS configuration...')
        response = ds_client.update_radius(
            DirectoryId = directory_service_id,
            RadiusSettings = radius_settings
        )


    # Now get the status; updating the directory service is asynchronous.
    MAX_ATTEMPTS = 30
    SLEEP_TIME = 5
    attempt_number = 1

    while attempt_number <= MAX_ATTEMPTS:
        response = ds_client.describe_directories(DirectoryIds=[directory_service_id])['DirectoryDescriptions'][0]

        print("** ATTEMPT {}: {}".format(attempt_number, response['RadiusStatus']))

        if response['RadiusStatus'] == 'Completed':
            break
        elif response['RadiusStatus'] == 'Failed':
            break
        else:
            time.sleep(SLEEP_TIME)
            attempt_number +=1


#========================================
# function: get_instance_private_ip_addresses
#========================================
def get_instance_private_ip_addresses(tagvalue):

    instance_private_ip_addresses = []

    # Get the private IP addressess of instances with the given characteristics:
    # 1. Tagged with directory service ID.
    # 2. Tagged with teh RadiusConfigured=True tag, which is applied by the
    #    "UpdateDirectoryServiceMfaSettings" Lambda function.
    #.3. The instance state is running.
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:duo:DirectoryServiceId", "Values": [tagvalue]},
            {"Name": "tag:RadiusConfigured", "Values": ["True"]},
            {"Name": "instance-state-name", "Values": ["running"]}
        ]
        )

    for reservation in (response["Reservations"]):
        for instance in reservation['Instances']:
            instance_private_ip_addresses.append(instance["PrivateIpAddress"])

    return instance_private_ip_addresses


#========================================
# function: get_directory_service_radius_status
#========================================
def get_directory_service_radius_status(directory_service_id):

    return_value = -1

    try:
        response = ds_client.describe_directories(DirectoryIds=[directory_service_id])['DirectoryDescriptions'][0]

        if 'RadiusStatus' not in response:
            return_value = RadiusStatus.NotConfigured
        elif response['RadiusStatus'] == 'Completed':
            return_value = RadiusStatus.Completed
        elif response['RadiusStatus'] == 'Failed':
            return_value = RadiusStatus.Failed
        elif response['RadiusStatus'] == 'Creating':
            return_value = RadiusStatus.Creating

    except:
        pass

    return return_value


#========================================
# function: get_radius_shared_secret
#========================================
def get_radius_shared_secret(radius_shared_secret_arn):

    radius_shared_secret = ''

    # Get the decrypted RADIUS shared secret value.
    response = secretsmanager_client.get_secret_value(
        SecretId = radius_shared_secret_arn
    )

    if 'SecretString' in response:
        radius_shared_secret = json.loads(response['SecretString'])['RadiusSharedSecret']

    return radius_shared_secret

