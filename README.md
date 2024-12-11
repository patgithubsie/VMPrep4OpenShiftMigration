# VM Preparation Script for Migration from VMware ESXi to OpenShift Virtualization

## Introduction
This Python script configures a VM running on VMware ESXi infrastructure with all the necessary settings to prepare it for warm migration to OpenShift Virtualization.

The actual "warm" migration can then be performed using the OpenShift Migration Toolkit for Virtualization (MTV). By using this script, there is no need to manually power off the VM before the final cutover, which would otherwise be required when modifying the CBT settings manually.

The only manual step required before starting the migration is installing VMware Tools on the source VM (if not already installed). For Linux systems, the easiest method is to install and start Open VM Tools. For example, on RHEL:
````
dnf install open-vm-tools
systemctl --now enable vmtoolsd
````

When executing the script, it will:
* Rename the VM to lowercase for RFC conformity
* Delete all existing snapshots
* Set the disk mode of all virtual disks to persistent 
* Enable Change Block Tracking (CBT) for the VM and all of its disks

The script automatically applies the following advanced VM parameters:
````
# turn on CBT
ctkEnabled TRUE
# turn on CBT for every existing disk (scsi0:n.ctkEnabled)
# for example if there are two virtual disks:
scsi0:0.ctkEnabled TRUE
scsi0:1.ctkEnabled TRUE
````

## Configuration
Before running the script for the first time, create a .env file containing the following information:
* The FQDN or IP address of the vCenter server
* A username and password with sufficient privileges to modify VM settings

If the file is incomplete or missing, the script will prompt you to enter any missing values each time it runs.
Should you choose to include your password in the file, ensure that the file is properly protected at all times. You can use the following lines as a template for the .env file:
````
# contents of .env file
SERVER = "vcenter.example.com"
USER = "your-vcenter-username"
PASSWORD = "your-password"
````

You must either install the dependencies listed in requirements.txt system-wide or, preferably, create a virtual environment for this script using the following steps (recommended):
````
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
````

## Running the script
After completing the preconfiguration and activating your virtual environment as described above, you can run the script. To do so, pass the name of the VM that needs to be reconfigured as the first parameter. Note that the VM name is case-sensitive.

Example usage:
````
python VMPrep4OpenShiftMigration.py MYVMNAME
````

