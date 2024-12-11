from dotenv import dotenv_values
from pwinput import pwinput
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import ssl
import sys

# Disable SSL warnings
context = ssl._create_unverified_context()


def connect_to_vcenter(server, user, password):
    """
    Connects to VCenter server and returns the service instance object
    """
    try:
        service_instance = SmartConnect(
            host=server,
            user=user,
            pwd=password,
            sslContext=context
        )
        print(f"Connected to {server}")
        return service_instance
    except Exception as e:
        print(f"Failed to connect to {server}: {e}")
        exit(1)


def find_vm_by_name(content, vm_name):
    """
    Find the VM by name on ESXi server (case sensitive)
    """
    obj_view = content.viewManager.CreateContainerView(
        content.rootFolder,
        [vim.VirtualMachine],
        True
    )
    vm_list = obj_view.view
    obj_view.Destroy()
    for vm in vm_list:
        if vm.name == vm_name:
            return vm
    return None


def rename_vm(vm, new_name):
    """
    Renames a VM to a new name
    """
    try:
        print(f"Renaming VM '{vm.name}' to '{new_name}'")
        task = vm.Rename(new_name)
        wait_for_task(task)
        print("Rename completed.")
    except Exception as e:
        print(f"Renaming the VM failed: {e}")


def enable_cbt_for_vm(vm):
    """
    Enable Change Block Tracking settings on VM
    """
    try:
        # Get the VM config spec
        config_spec = vim.vm.ConfigSpec()
        config_spec.changeTrackingEnabled = True

        # Reconfigure the VM
        print("Enabling CBT...")
        task = vm.ReconfigVM_Task(config_spec)
        wait_for_task(task)
        print("CBT enabled successfully.")
    except Exception as e:
        print(f"Error enabling CBT: {e}")


def count_snapshots(snapshots):
    """
    Recursively count all snapshots in the snapshot tree.
    """
    count = len(snapshots)
    for snapshot in snapshots:
        count += count_snapshots(snapshot.childSnapshotList)
    return count


def delete_snapshots(vm):
    snapshot_info = vm.snapshot
    if snapshot_info is None:
        print(f"No snapshots found for VM '{vm.name}'.")
    else:
        snapshot_count = count_snapshots(snapshot_info.rootSnapshotList)
        print(f"Found {snapshot_count} snapshots, deleting them...")
        try:
            task = vm.RemoveAllSnapshots_Task()
            wait_for_task(task)
            print("All snapshots deleted.")
        except Exception as e:
            print(f"Failed to remove snapshost {e}")


def check_and_update_disk_mode(vm):
    """
    Check if any virtual disks are not in 'dependent' mode and update them.
    """
    config = vm.config
    devices = config.hardware.device

    for device in devices:
        if isinstance(device, vim.vm.device.VirtualDisk):
            backing = device.backing
            if hasattr(backing, 'diskMode') and backing.diskMode != 'persistent':
                print(f"Disk {device.deviceInfo.label} is in {backing.diskMode} mode.")
                update_disk_mode(vm, device, 'persistent')


def update_disk_mode(vm, disk, new_mode):
    """
    Update the disk mode of a virtual disk.
    """
    spec = vim.vm.ConfigSpec()
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
    disk_spec.device = disk
    disk_spec.device.backing.diskMode = new_mode

    spec.deviceChange = [disk_spec]

    print(f"Updating disk {disk.deviceInfo.label} to mode {new_mode}...")
    task = vm.Reconfigure(spec)
    wait_for_task(task)
    print(f"Disk {disk.deviceInfo.label} updated to {new_mode} mode.")


def wait_for_task(task):
    while task.info.state == vim.TaskInfo.State.running:
        continue
    if task.info.state == vim.TaskInfo.State.success:
        print("Task completed successfully.")
    else:
        print(f"Task did not complete successfully: {task.info.error}")


def main():
    # Fetch VM name from first command arg
    if len(sys.argv) == 2:
        vm_name = sys.argv[1]
    else:
        print(f"Usage: python {sys.argv[0]} MYVMNAME")
        sys.exit(1)

    # Load configuration from .env
    config = dotenv_values(".env")
    config_required = ["SERVER", "USER", "PASSWORD"]
    config_missing = [k for k in config_required if k not in config]
    # Check if there are missing environment variables
    if len(config_missing) > 0:
        print(
            f"Environment variable(s) are missing: {', '.join(config_missing)}\n"
            "Set these values in your .env file as described in README.md "
            "to avoid entering them manually each time.\n"
        )
        # Prompt for all missing variables, mask password
        for v in config_missing:
            prompt = f"Please enter {v}: "
            config[v] = pwinput(prompt) if v == "PASSWORD" else input(prompt)

    # Connect to VCenter
    service_instance = connect_to_vcenter(
        server=config["SERVER"],
        user=config["USER"],
        password=config["PASSWORD"]
    )
    content = service_instance.RetrieveContent()

    # Try to find the VM by name
    vm = find_vm_by_name(content, vm_name)
    if vm:
        print(f"Found VM: {vm.name}")
        # Rename the VM to lowercase if required (RFC conformity)
        if vm_name.islower():
            print("VM name already lowercase, no need to rename.")
        else:
            rename_vm(vm, vm_name.lower())
        # Fetch and delete all existing Snapshots (if any)
        delete_snapshots(vm)
        # Check and update disks to dependent mode if required
        check_and_update_disk_mode(vm)
        # Enable CBT for VM and all of it's disks
        enable_cbt_for_vm(vm)
    else:
        print(f"VM '{vm_name}' not found.")

    # Disconnect from VCenter
    Disconnect(service_instance)


if __name__ == "__main__":
    main()
