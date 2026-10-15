"""Find the serial port of a USB device by vendor ID (macOS), so tools never open another device."""
import re, subprocess

def find_port(vid):
    try:
        tree = subprocess.run(['ioreg', '-r', '-c', 'IOUSBHostDevice', '-l', '-w0'], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return None
    for dev in re.split(r'^\+-o ', tree, flags=re.M):
        if f'"idVendor" = {vid}' in dev:
            m = re.search(r'"IOCalloutDevice" = "([^"]+)"', dev)
            if m:
                return m.group(1)
    return None
