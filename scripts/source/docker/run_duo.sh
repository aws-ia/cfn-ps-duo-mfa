#!/bin/bash

set -e

while read -rd $'' line
do
    export "$line"
done < <(jq -r <<<"$DuoSecret" \
         'to_entries|map("\(.key)=\(.value)\u0000")[]')

if [ $AD_SYNC == 'yes' ]
then
    echo 'Building config with AD sync'
    cat > /opt/duoauthproxy/conf/authproxy.cfg <<-EOL
    [main]
    fips_mode=true

    [cloud]
    ikey=$DirectoryIntegrationKey
    skey=$DirectorySecretKey
    api_host=$DuoApiHostName
    service_account_username=$adReadOnlyUser
    service_account_password=$adReadOnlyPassword

    [radius_server_duo_only]
    ikey=$DuoIntegrationKey
    skey=$DuoSecretKey
    api_host=$DuoApiHostName
    failmode=$DUO_FAIL_MODE
    port=$RADIUS_PORT_NUMBER
    radius_ip_1=$DIRECTORY_IP1
    radius_secret_1=$RadiusSharedSecret
    radius_ip_2=$DIRECTORY_IP2
    radius_secret_2=$RadiusSharedSecret
EOL

elif [ $AD_SYNC == 'no' ]
then 
    echo 'Building config without AD sync'
    cat > /opt/duoauthproxy/conf/authproxy.cfg <<-EOL
    [main]
    fips_mode=true

    [radius_server_duo_only]
    ikey=$DuoIntegrationKey
    skey=$DuoSecretKey
    api_host=$DuoApiHostName
    failmode=$DUO_FAIL_MODE
    port=$RADIUS_PORT_NUMBER
    radius_ip_1=$DIRECTORY_IP1
    radius_secret_1=$RadiusSharedSecret
    radius_ip_2=$DIRECTORY_IP2
    radius_secret_2=$RadiusSharedSecret
EOL
else 
    echo 'AD Sync environment variable should be yes/no. Found the value to be ${AD_SYNC}'
    exit 1
fi

/opt/duoauthproxy/bin/authproxyctl restart
tail -100f /opt/duoauthproxy/log/authproxy.log
