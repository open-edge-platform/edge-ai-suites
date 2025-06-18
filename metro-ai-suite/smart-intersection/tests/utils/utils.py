import subprocess

def run_command(cmd):
    """Run a shell command and return (stdout, stderr, returncode)."""
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return out.decode(), err.decode(), proc.returncode