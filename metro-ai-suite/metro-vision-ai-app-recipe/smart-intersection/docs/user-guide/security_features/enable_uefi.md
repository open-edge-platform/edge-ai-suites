# Enabling UEFI Secure Boot for Smart Intersection

UEFI Secure Boot establishes a chain of trust from firmware to OS, cryptographically verifying the signature and hash of all boot components before passing control to the operating system. This ensures the Smart Intersection application runs on a verified, secure platform.

Ubuntu LTS official releases are signed by Canonical, and Canonical's certificate is pre-enrolled in the MOK (Machine Owner Key) database.

## Step 1: Install Required Tools

```bash
sudo apt update
sudo apt upgrade
sudo apt-get install -y openssl mokutil sbsigntool
```

## Step 2: Verify Kernel Signature

```bash
sudo sbverify --list /boot/vmlinuz-<kernel_version>-generic
```

![Kernel Signature Verification](../_images/security_kernel_signature_verification.png)

**Step 3: Verify Certificate Enrollment**

```bash
mokutil --list-enrolled
```

![MOK Database Certificate List](../_images/security_mok_database_certificate_list.png)

## Step 3: Install Signed Shim Binary

Most UEFI firmware has Microsoft keys enrolled by default. To verify GRUB and Linux kernel signed by Canonical, install the signed shim binary. Shim is a small bootloader signed by Microsoft that bridges the gap between firmware and Linux GRUB, maintaining the chain of trust.

```bash
sudo apt-get install sbsigntool openssl grub-efi-amd64-signed shim-signed
sudo grub-install --uefi-secure-boot
```

## Step 4: Configure Secure Boot**

1. Reboot the platform and enter the UEFI GUI menu
2. Verify that Secure Boot is initially disabled
3. Confirm the shim binary can boot to OS

## Step 5: Enroll Microsoft Certificates**

1. Get the Secure Boot Microsoft keys and certificates:
```bash
git clone https://git.launchpad.net/qa-regression-testing
```

2. Enroll the certificates (type 'y' when prompted):
```bash
cd qa-regression-testing/notes_testing/secure-boot
cp -rf * /tmp
sudo /tmp/sb-setup enroll microsoft
```

> **Note**: If enrollment errors occur, reboot the platform, boot using `fs0:/efi/ubuntu/shimx64.efi`, and rerun the enroll command.

## Step 6: Enable and Verify Secure Boot**

1. Reboot the platform and enter the BIOS menu
2. Verify that Secure Boot is now enabled
3. Boot using `fs0:/efi/ubuntu/shimx64.efi`
4. Check the Secure Boot status after booting to Ubuntu:

```bash
mokutil --sb-state
```

![Secure Boot Status Verification](../_images/security_secure_boot_status_verification.png)

### TPM Clear Operation

TPM clear removes all stored keys, certificates, and ownership data from the Trusted Platform Module, resetting it to factory defaults. This is useful when setting up security for a new Smart Intersection deployment.

1. Enter the boot manager menu
2. Choose the TCG2 configuration 
3. Clear the TPM

![TPM Clear Configuration Menu](../_images/security_tpm_clear_configuration_menu.png)
