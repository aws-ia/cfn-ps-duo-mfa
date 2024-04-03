#!/bin/bash -ex

aws sts get-caller-identity --debug

# project root directory path
project_root="${BASE_PATH}/project"
# automation scripts directory path
automation_scripts_path="${project_root}/.project_automation/publication/assets/"
# project taskcat config filename
project_config_file="${project_root}/.taskcat.yml"

prepare_taskcat_file_to_publish(){
    # modified taskcat config filename for publishing
    modified_config_file="${automation_scripts_path}.taskcat_publish.yml"

    # name of the attribute to retrieve from project config file
    attr_name=".project.name"

    # retrieve the value of the attribute from the project config yml file
    attr_value=$(yq -r "${attr_name}" ${project_config_file})

    # add the attribute and its value to the modified_config_file
    yq -Y --arg attribute_name "name" --arg attribute_value "${attr_value}" '.project += {($attribute_name): ($attribute_value)}' ${modified_config_file} > "${automation_scripts_path}tmp.yml"
}

prepare_aws_config(){
    # set defaults
    secret_name="aws_config.override"
    secret_region="us-east-1"

    # get aws config override file from secrets manager
    json_overrides=$(aws secretsmanager get-secret-value --secret-id ${secret_name} --query SecretString --output text --region ${secret_region})

    # parse JSON using jq and iterate over each profile
    profiles=$(echo "${json_overrides}" | jq -r '.profiles | keys[]')

    # create default profile and redirect output to a file
    echo -e "[profile default]\ncredential_process = cat \"${BASE_PATH}/.aws/temp-creds-default.json\"" > "${automation_scripts_path}aws_config.override"

    for profile in ${profiles}
    do
        # get values of each profile
        region=$(echo "${json_overrides}" | jq -r ".profiles[\"${profile}\"].region")
        credential=$(echo "${json_overrides}" | jq -r ".profiles[\"${profile}\"].credential_process // .profiles[\"${profile}\"].credential_source")

        # print the profile and its values in the desired format
        echo -e "\n[profile ${profile}]\nregion = ${region}\ncredential_process = ${credential}" >> "${automation_scripts_path}aws_config.override"
        sed -i "s|project_root|${project_root}|g" "${automation_scripts_path}aws_config.override"
    done
}

# package lambdas
taskcat package -p ${project_root} -s functions/source/ -z functions/packages/

prepare_taskcat_file_to_publish
prepare_aws_config

export AWS_CONFIG_FILE="${automation_scripts_path}aws_config.override"

cat ${AWS_CONFIG_FILE}
cat "${automation_scripts_path}tmp.yml"

aws sts get-caller-identity --debug

chmod 755 ${project_root}/.project_automation/publication/assets/cred_helper.py
# push to regional S3 buckets
export TASKCAT_PROJECT_S3_REGIONAL_BUCKETS=true; taskcat -d upload -p ${project_root} -c "${automation_scripts_path}tmp.yml"