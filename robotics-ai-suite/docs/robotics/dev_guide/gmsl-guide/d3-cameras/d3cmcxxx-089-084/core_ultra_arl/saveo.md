# SEAVO HB03 with D3CMCXXX-089-084

> **Note:** SEAVO HB03 supports up to 4x GMSL2 camera interfaces.

## i2cdetect usage

Use i2cdetect from i2c-tools to verify I2C bus to GMSL2 deserializer and serializer ACPI device mapping.

```bash
i2cdetect -y <i2c_bus_number>
```

To perform a bounded scan:

```bash
i2cdetect -r -y <i2c_bus_number> 0x20 0x6f
```

No SEAVO-specific ACPI table for D3CMCXXX-089-084 is currently documented in configure-gmsl-serdes-acpi.md.
