# Axiomtek ROBOX500 with D3CMCXXX-089-084

> **Note:** Axiomtek ROBOX500 supports either 4x or 8x GMSL camera interfaces.

## i2cdetect usage

Use i2cdetect from i2c-tools to verify I2C bus to GMSL2 deserializer and serializer ACPI device mapping.

```bash
i2cdetect -y <i2c_bus_number>
```

To perform a bounded scan:

```bash
i2cdetect -r -y <i2c_bus_number> 0x20 0x6f
```

No Axiomtek-specific ACPI table for D3CMCXXX-089-084 is currently documented in configure-gmsl-serdes-acpi.md.
