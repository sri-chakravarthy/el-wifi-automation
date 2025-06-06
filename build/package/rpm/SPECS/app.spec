%define date %(date +"%Y%m%d")
%global debug_package %{nil}

%define commit %{getenv:GITHUB_REF_NAME}
%define version %{getenv:GITHUB_REF_NAME}
%define release %{getenv:RELEASE}
%define appname %{getenv:APP_NAME}
%define giturl %{getenv:GITHUB_SERVER_URL}/%{getenv:GITHUB_REPOSITORY}
%define gitdesc %{getenv:GITHUB_REPOSITORY}
%define containerimage %{getenv:CONTAINER_REGISTRY}/%{getenv:APP_NAME}
%define rpmname %{getenv:RPM_NAME}
%define appusername %{getenv:APP_USER_USERNAME}
%define appuid %{getenv:APP_USER_ID}


%define pas %{getenv:RUN_ON_PAS}
%define hsa %{getenv:RUN_ON_HSA}
%define dnc %{getenv:RUN_ON_DNC}
%define fips %{getenv:RUN_ON_FIPS}

Name:		%{rpmname}
Version:	%{version}
%if 0%{release}
Release:	%{release}%{?dist}
%else
Release:	1%{?dist}
%endif
Summary:	%{gitdesc}
Group:		SevOne/ps-addon
License:	Proprietary
URL:		%{giturl}
Source0:	app

#Requires:   systemd
#Requires:   supervisor
#Requires:	/usr/bin/docker
Requires:   curl
Requires:   grep

%description
%{gitdesc}


%install
mkdir -p %{buildroot}/var/custom/ps-addon/%{appname}/env
mkdir -p %{buildroot}/var/custom/ps-addon/%{appname}/bin
mkdir -p %{buildroot}/var/custom/ps-addon/%{appname}/container
mkdir -p %{buildroot}/var/custom/ps-addon/%{appname}/etc
mkdir -p %{buildroot}/var/custom/ps-addon/%{appname}/log
#mkdir -p %{buildroot}/var/custom/ps-addon/%{appname}/src
#mkdir -p %{buildroot}/var/custom/ps-addon/%{appname}/incoming
#mkdir -p %{buildroot}/var/custom/ps-addon/%{appname}/archive


/bin/sed -i "s,APPNAMEREPLACE,%{appname},g" %{SOURCE0}/bin/run-wifi-automations.sh
#/bin/sed -i "s,CONTAINERIMAGEREPLACE,%{containerimage},g" %{SOURCE0}/etc/cronjob.yml
#/bin/sed -i "s,CONTAINERIMAGEVERSIONREPLACE,%{commit},g" %{SOURCE0}/etc/cronjob.yml



#mkdir -p %{buildroot}/var/custom/ps-addon/%{appname}/imports
cp %{SOURCE0}/%{appname}.%{version}.tar %{buildroot}/var/custom/ps-addon/%{appname}/container/%{appname}-%{version}.tar
#cp %{SOURCE0}/* %{buildroot}/var/custom/ps-addon/%{appname}/
#cp %{SOURCE0}/app.env.example %{buildroot}/var/custom/ps-addon/%{appname}/env/.ibm-el-%{appname}.env.example
#cp %{SOURCE0}/sample-config.json %{buildroot}/var/custom/ps-addon/%{appname}/etc/sample-config.json
cp -r %{SOURCE0}/bin/* %{buildroot}/var/custom/ps-addon/%{appname}/bin/
cp -r %{SOURCE0}/env/* %{buildroot}/var/custom/ps-addon/%{appname}/env/
cp -r %{SOURCE0}/etc/* %{buildroot}/var/custom/ps-addon/%{appname}/etc/
#cp -r %{SOURCE0}/src/* %{buildroot}/var/custom/ps-addon/%{appname}/src/
#mv %{SOURCE0}/etc/cronjob.yml %{buildroot}/var/custom/ps-addon/%{appname}/
#rm %{buildroot}/opt/SevOne/%{appname}/etc/cronjob.yml



%files
%dir /var/custom/ps-addon/%{appname}/
#%dir /opt/SevOne/%{appname}/incoming
#%dir /opt/SevOne/%{appname}/archive
/var/custom/ps-addon/%{appname}/container/%{appname}-%{commit}.tar
#/opt/SevOne/%{appname}/env/.ibm-el-%{appname}.env.example
#/opt/SevOne/%{appname}/env/key.txt
#/opt/SevOne/%{appname}/etc/*.json
#/opt/SevOne/%{appname}/etc/*.csv
/var/custom/ps-addon/%{appname}/bin/*
#/opt/SevOne/%{appname}/src/*.py
#/opt/SevOne/%{appname}/cronjob.yml
/var/custom/ps-addon/%{appname}/etc/*
/var/custom/ps-addon/%{appname}/env/*



%pre

#getent group %{appusername}  &>/dev/null
#if [ $? -ne 0 ]; then
#    echo "---   Creating user group for plugin: %{appusername}"
#    groupadd -g %{appuid} %{appusername}
#fi
#getent passwd %{appusername}  &>/dev/null
#if [ $? -ne 0 ]; then
#    echo "---   Creating user for plugin: %{appusername}"
#    useradd -c 'PS AddOn User' -u %{appuid} -g %{appuid} -M -N -s /sbin/nologin %{appusername}
#fi

%post

# Copy sample configuration file
if [ ! -f "/var/custom/ps-addon/%{appname}/config.json" ]; then
    if [ ! -f "/var/custom/ps-addon/%{appname}/sample-config.json" ]; then
        touch /var/custom/ps-addon/%{appname}/config.json
    else
        cp /var/custom/ps-addon/%{appname}/sample-config.json /var/custom/ps-addon/%{appname}/config.json
    fi
else
    cp  /var/custom/ps-addon/%{appname}/config.json  /var/custom/%{appname}/ps-addon/config.json_orig_%{commit}
    cp  /var/custom/ps-addon/%{appname}/sample-config.json /var/custom/ps-addon/%{appname}/config.json
fi

#chown -R %{appusername}:%{appusername} /var/custom/ps-addon/%{appname}
#chmod +x /var/custom/ps-addon/%{appname}/*.py

#if /usr/local/bin/kubectl get cronjob %{appname}  > /dev/null 2>&1; then
#    echo "---   Deleting kubernetes cronjob %{appname}"
#    /usr/local/bin/kubectl delete cronjob %{appname}
#fi

#Create a config map
#echo "---   Creating kubernetes config map env-config"
#HOST_IP=$(hostname -I | awk '{print $1}')
#CONFIGMAP_NAME="env-config"
# Check if the ConfigMap exists
#if ! kubectl get configmap "$CONFIGMAP_NAME" > /dev/null 2>&1; then
#    /usr/local/bin/kubectl create configmap env-config --from-literal=HOST_IP=$HOST_IP
#fi

# Before loading new image, delete any old previous images
echo "---   Removing any previous container images for %{appname}"
for image in $(sudo /usr/bin/podman image list | grep {appname} | awk '{print $1}'); do
   sudo /usr/bin/podman images rm $image
done
echo "---   Removed old container images for %{appname}"
echo "---   Loading the container image for %{appname} %{commit}"
sudo /usr/bin/podman load -i /var/custom/ps-addon/%{appname}/container/%{appname}-%{commit}.tar
echo "---   Loaded the container image for %{appname} %{commit}"

#echo "---   Creating kubernetes cronjob %{appname}"
#/usr/local/bin/kubectl apply -f /opt/SevOne/%{appname}/cronjob.yml
#echo "---   Created kubernetes cronjob %{appname}"
#echo "---   Please check the  %{appname}/cronjob.yml file for the schedule"

%preun
#if [ $1 -eq 0 ]; then
#    # Package removal, not upgrade
#    echo "---   Stopping %{name} %{version}"
#    /usr/local/bin/kubectl delete cronjob %{appname}
#    #echo "---   Stopping %{appname} %{commit}"

#    echo "---   deleting Config map "
#    /usr/local/bin/kubectl delete configmap env-config
#    #echo "---   Deleted config map"

#fi

%postun

if pgrep -x "podman" > /dev/null
then
    echo "---   Removing the container image for %{appname} %{commit} (%{containerimage}:%{commit})"
    sudo podman rmi -f %{containerimage}:%{commit}
    echo "---   Removed the container image for %{appname} %{commit} (%{containerimage}:%{commit})"
    echo "--- Removing the app related directories"
    rm -rf /var/custom/ps-addon/%{appname}/
fi

