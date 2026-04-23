# Configure Intel® GMSL `SerDes` ACPI Devices

To enable multiple GMSL cameras, for the same or different vendors, define the MIPI camera ACPI device in UEFI/BIOS settings.

1. Review Intel®-enabled GMSL2 camera modules with their corresponding ACPI device custom HIDs:

   | ACPI custom HID | Camera module label | Sensor type         | GMSL2 serializer | Max resolution | Vendor URL                                                                             |
   | --------------- | ------------------- | ------------------- | ---------------- | -------------- | -------------------------------------------------------------------------------------- |
   | `INTC10CD`      | `d4xx`              | OV9782 + D450 Depth | MAX9295          | 2x (1280x720)  | [Intel® RealSense Depth Camera D457](https://realsenseai.com/products/d457-gmsl-fakra) |
   | `D3000004`      | `D3CMCXXX-115-084`  | ISX031              | MAX9295          | 1920x1536      | [D3 Embedded](https://www.d3embedded.com/)                                             |
   | `D3000005`      | `D3CMCXXX-106-084`  | IMX390              | MAX9295          | 1920x1080      | sensor Linux drivers package available upon `sales@d3embedded.com` camera purchase     |
   | `D3000006`      | `D3CMCXXX-089-084`  | AR0234              | MAX9295          | 1280x960       |                                                                                        |
   | `OTOC1031`      | `otocam`            | ISX031              | MAX9295          | 1920x1536      | [oToBrite](https://www.otobrite.com/)                                                  |
   | `OTOC1021`      | `otocam`            | ISX021              | MAX9295          | 1920x1280      | sensor Linux drivers package available upon `sales@otobrite.com` camera purchase       |

2. Review the [GMSL Add-in-Card Design Overview](./gmsl-aic-overview.md), if not already done.

   Refer to each tab below to understand the distinct ACPI camera device configuration tables for ODM hardware.

   <!--hide_directive::::::{tab-set}
   :::::{tab-item}hide_directive--> **Advantech® AFE-R360 & ASR-A502 series**

   The [Advantech® GMSL Input Module Card](https://www.advantech.com/en-eu/products/8d5aadd0-1ef5-4704-a9a1-504718fb3b41/mioe-gmsl/mod_fc1fc070-30f8-40c1-881f-56c967e26924) for [AFE-R360 series](https://www.advantech.com/en-eu/products/8d5aadd0-1ef5-4704-a9a1-504718fb3b41/afe-r360/mod_1e4a1980-9a31-46e6-87b6-affbd7a2cb44) and [ASR-A502 series](https://www.advantech.com/en-eu/products/8d5aadd0-1ef5-4704-a9a1-504718fb3b41/asr-a502/mod_ccca0f36-a50b-40c7-87b7-10fb96448605) may provide up to 6x GMSL camera interfaces (FAKRA universal type).

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **RealSense™ D457**
   <!--hide_directive:sync: realsensehide_directive-->

   Below is an ACPI device configuration example for the GMSL2 Intel® RealSense Depth Camera D457:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
   | ------------------- | ---------- | ---------- | ---------- | ---------- |
   | GMSL Camera suffix  | a          | g          | e          | k          |
   | Custom HID          | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` |
   | PPR Value           | 2          | 2          | 2          | 2          |
   | PPR Unit            | 1          | 1          | 1          | 1          |
   | Camera module label | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     |
   | MIPI Port (Index)   | 0          | 0          | 4          | 4          |
   | LaneUsed            | x2         | x2         | x2         | x2         |
   | Number of I2C       | 3          | 3          | 3          | 3          |
   | I2C Channel         | I2C1       | I2C1       | I2C2       | I2C2       |
   | Device0 I2C Address | 12         | 14         | 12         | 14         |
   | Device1 I2C Address | 42         | 44         | 42         | 44         |
   | Device2 I2C Address | 48         | 48         | 48         | 48         |

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **D3CMCXXX-115-084**
   <!--hide_directive:sync: d3cmc115hide_directive-->

   Below is an ACPI device configuration example for the [D3 Embedded Discovery](https://www.d3embedded.com/product/isx031-smart-camera-narrow-fov-gmsl2-unsealed/) GMSL2 camera module:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1           | Camera 2           |
   | ------------------- | ------------------ | ------------------ |
   | GMSL Camera suffix  | a                  | e                  |
   | Custom HID          | `D3000004`         | `D3000004`         |
   | PPR Value           | 2                  | 2                  |
   | PPR Unit            | 2                  | 2                  |
   | Camera module label | `D3CMCXXX-115-084` | `D3CMCXXX-115-084` |
   | MIPI Port (Index)   | 0                  | 4                  |
   | LaneUsed            | x2                 | x2                 |
   | Number of I2C       | 3                  | 3                  |
   | I2C Channel         | I2C1               | I2C2               |
   | Device0 I2C Address | 48                 | 48                 |
   | Device1 I2C Address | 42                 | 44                 |
   | Device2 I2C Address | 10                 | 12                 |

   > **Note:** on Advantech® AFE-R360 series the four D3CMCXXX ACPI configurations achieved by `PPR Unit=2` also require setting `Device0` for the GMSL2 **aggregated-link** deserializer I2C address, for example `MAX9296A`, and `Device2` for the sensor I2C address, for example `ISX031`.

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **D3CMCXXX-106-084**
   <!--hide_directive:sync: d3cmc106hide_directive-->

   Below is an ACPI device configuration example for the [D3 Embedded Discovery PRO](https://www.d3embedded.com/product/imx390-medium-fov-gmsl2-sealed/) GMSL2 camera module:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1           | Camera 2           |
   | ------------------- | ------------------ | ------------------ |
   | GMSL Camera suffix  | a                  | e                  |
   | Custom HID          | `D3000005`         | `D3000005`         |
   | PPR Value           | 2                  | 2                  |
   | PPR Unit            | 2                  | 2                  |
   | Camera module label | `D3CMCXXX-106-084` | `D3CMCXXX-106-084` |
   | MIPI Port (Index)   | 0                  | 4                  |
   | LaneUsed            | x2                 | x2                 |
   | Number of I2C       | 3                  | 3                  |
   | I2C Channel         | I2C1               | I2C2               |
   | Device0 I2C Address | 48                 | 48                 |
   | Device1 I2C Address | 42                 | 44                 |
   | Device2 I2C Address | 10                 | 12                 |

   > **Note:** on Advantech® AFE-R360 series the four D3CMCXXX ACPI configurations achieved by `PPR Unit=2` also require setting `Device0` for the GMSL2 **aggregated-link** deserializer I2C address, for example `MAX9296A`, and `Device2` for the sensor I2C address, for example `ISX031`.

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **oToCAM222**
   <!--hide_directive:sync: otocam222hide_directive-->

   Below is an ACPI device configuration example for [oToBrite oToCAM222](https://www.otobrite.com/product/automotive-camera/isx021_gmsl2_otocam222-s195m) GMSL2 camera modules:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
   | ------------------- | ---------- | ---------- | ---------- | ---------- |
   | GMSL Camera suffix  | a          | g          | e          | k          |
   | Custom HID          | `OTOC1021` | `OTOC1021` | `OTOC1021` | `OTOC1021` |
   | PPR Value           | 2          | 2          | 2          | 2          |
   | PPR Unit            | 1          | 1          | 1          | 1          |
   | Camera module label | `otocam`   | `otocam`   | `otocam`   | `otocam`   |
   | MIPI Port (Index)   | 0          | 0          | 4          | 4          |
   | LaneUsed            | x2         | x2         | x2         | x2         |
   | Number of I2C       | 3          | 3          | 3          | 3          |
   | I2C Channel         | I2C1       | I2C1       | I2C2       | I2C2       |
   | Device0 I2C Address | 10         | 11         | 10         | 11         |
   | Device1 I2C Address | 18         | 19         | 18         | 19         |
   | Device2 I2C Address | 48         | 48         | 48         | 48         |

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **oToCAM223**
   <!--hide_directive:sync: otocam223hide_directive-->

   Below is an ACPI device configuration example for [oToBrite oToCAM223](https://www.otobrite.com/product/automotive-camera/isx031_gmsl2_otocam223-s195m) GMSL2 camera modules:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
   | ------------------- | ---------- | ---------- | ---------- | ---------- |
   | GMSL Camera suffix  | a          | g          | e          | k          |
   | Custom HID          | `OTOC1031` | `OTOC1031` | `OTOC1031` | `OTOC1031` |
   | PPR Value           | 2          | 2          | 2          | 2          |
   | PPR Unit            | 1          | 1          | 1          | 1          |
   | Camera module label | `otocam`   | `otocam`   | `otocam`   | `otocam`   |
   | MIPI Port (Index)   | 0          | 0          | 4          | 4          |
   | LaneUsed            | x2         | x2         | x2         | x2         |
   | Number of I2C       | 3          | 3          | 3          | 3          |
   | I2C Channel         | I2C1       | I2C1       | I2C2       | I2C2       |
   | Device0 I2C Address | 10         | 11         | 10         | 11         |
   | Device1 I2C Address | 18         | 19         | 18         | 19         |
   | Device2 I2C Address | 48         | 48         | 48         | 48         |

   <!--hide_directive:::
   ::::hide_directive-->

   ![Advantech GMSL layout](../../images/gmsl/gmsl-adv-mioe.png "advantech gmsl layout")

   Another example below illustrates how to configure ACPI devices for 6x Intel® RealSense Depth Camera D457 GMSL2 modules:

   _**Aggregated-link** `SerDes` CSI-2 port 0, 4 and 5 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   | Camera 5 or N/A | Camera 6 or N/A |
   | ------------------- | ---------- | ---------- | ---------- | ---------- | --------------- | --------------- |
   | GMSL Camera suffix  | a          | g          | e          | f          | _k_             | _l_             |
   | Custom HID          | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD`      | `INTC10CD`      |
   | PPR Value           | 2          | 2          | 2          | 2          | 2               | 2               |
   | PPR Unit            | 1          | 1          | 1          | 1          | 1               | 1               |
   | Camera module label | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`          | `d4xx`          |
   | MIPI Port (Index)   | 0          | 0          | 4          | 5          | 4               | 5               |
   | LaneUsed            | x2         | x2         | x2         | x2         | x2              | x2              |
   | Number of I2C       | 3          | 3          | 3          | 3          | 3               | 3               |
   | I2C Channel         | I2C1       | I2C1       | I2C2       | I2C2       | _I2C2_          | _I2C2_          |
   | Device0 I2C Address | 12         | 14         | 16         | 18         | _12_            | _14_            |
   | Device1 I2C Address | 42         | 44         | 62         | 42         | _64_            | _44_            |
   | Device2 I2C Address | 48         | 48         | 48         | 4a         | _48_            | _4a_            |

   > **Attention:** For the time being, each GMSL2 **aggregated-link** deserializer, for example `MAX9296A`, on the same I2C channel must set an identical _Custom HID_ and _Camera module label_ tuple matching the GMSL2 serializer and camera sensor device type.
   >
   > For the [Advantech® GMSL Input Module Card](https://www.advantech.com/en-eu/products/8d5aadd0-1ef5-4704-a9a1-504718fb3b41/mioe-gmsl/mod_fc1fc070-30f8-40c1-881f-56c967e26924) for [AFE-R360 series](https://www.advantech.com/en-eu/products/8d5aadd0-1ef5-4704-a9a1-504718fb3b41/afe-r360/mod_1e4a1980-9a31-46e6-87b6-affbd7a2cb44), the I2C1-channel **aggregated-link** deserializer at I2C device `0x48` can set the _Custom HID_, for example `INTC10CD`, and _Camera module label_, for example `d4xx`, tuple for both GMSL camera suffixes `a` and `g`, while the other **aggregated-link** deserializer at I2C device `0x4a` can use a different _Custom HID_, for example `INTC1031`, and _Camera module label_, for example `isx031`, tuple on GMSL camera suffixes `e` and `k`.

   <!--hide_directive:::::
   :::::{tab-item}hide_directive--> **SEAVO® HB03**

   The [SEAVO® Embedded Computer HB03](https://www.seavo.com/en/products/products-info_itemid_693.html) UEFI BIOS `Version: S1132C1133A11` allows an admin user to configure up to 4x GMSL2 camera interfaces (FAKRA universal type).

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **RealSense™ D457**
   <!--hide_directive:sync: realsensehide_directive-->

   Below is an ACPI device configuration example for the GMSL2 Intel® RealSense Depth Camera D457:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
   | ------------------- | ---------- | ---------- | ---------- | ---------- |
   | GMSL Camera suffix  | a          | g          | e          | k          |
   | Custom HID          | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` |
   | PPR Value           | 2          | 2          | 2          | 2          |
   | PPR Unit            | 1          | 1          | 1          | 1          |
   | Camera module label | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     |
   | MIPI Port (Index)   | 0          | 0          | 4          | 4          |
   | LaneUsed            | x4         | x4         | x4         | x4         |
   | Number of I2C       | 3          | 3          | 3          | 3          |
   | I2C Channel         | I2C1       | I2C1       | I2C0       | I2C0       |
   | Device0 I2C Address | 12         | 14         | 12         | 14         |
   | Device1 I2C Address | 42         | 44         | 42         | 44         |
   | Device2 I2C Address | 48         | 48         | 48         | 48         |

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **D3CMCXXX-115-084**
   <!--hide_directive:sync: d3cmc115hide_directive-->

   Below is an ACPI device configuration example for the [D3 Embedded Discovery](https://www.d3embedded.com/product/isx031-smart-camera-narrow-fov-gmsl2-unsealed/) GMSL2 camera module:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1           | Camera 2           |
   | ------------------- | ------------------ | ------------------ |
   | GMSL Camera suffix  | a                  | e                  |
   | Custom HID          | `D3000004`         | `D3000004`         |
   | PPR Value           | 2                  | 2                  |
   | PPR Unit            | 2                  | 2                  |
   | Camera module label | `D3CMCXXX-115-084` | `D3CMCXXX-115-084` |
   | MIPI Port (Index)   | 0                  | 4                  |
   | LaneUsed            | x4                 | x4                 |
   | Number of I2C       | 3                  | 3                  |
   | I2C Channel         | I2C1               | I2C0               |
   | Device0 I2C Address | 48                 | 48                 |
   | Device1 I2C Address | 42                 | 44                 |
   | Device2 I2C Address | 10                 | 12                 |

   > **Note:** On SEAVO® HB03, the four D3CMCXXX ACPI configurations achieved by `PPR Unit=2` also require setting `Device0` for the GMSL2 **aggregated-link** deserializer I2C address, for example `MAX9296A`, and `Device2` for the sensor I2C address, for example `ISX031`.

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **D3CMCXXX-106-084**
   <!--hide_directive:sync: d3cmc106hide_directive-->

   Below is an ACPI device configuration example for the [D3 Embedded Discovery PRO](https://www.d3embedded.com/product/imx390-medium-fov-gmsl2-sealed/) GMSL2 camera module:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1           | Camera 2           |
   | ------------------- | ------------------ | ------------------ |
   | GMSL Camera suffix  | a                  | e                  |
   | Custom HID          | `D3000005`         | `D3000005`         |
   | PPR Value           | 2                  | 2                  |
   | PPR Unit            | 2                  | 2                  |
   | Camera module label | `D3CMCXXX-106-084` | `D3CMCXXX-106-084` |
   | MIPI Port (Index)   | 0                  | 4                  |
   | LaneUsed            | x4                 | x4                 |
   | Number of I2C       | 3                  | 3                  |
   | I2C Channel         | I2C1               | I2C0               |
   | Device0 I2C Address | 48                 | 48                 |
   | Device1 I2C Address | 42                 | 44                 |
   | Device2 I2C Address | 10                 | 12                 |

   > **Note:** On SEAVO® HB03, the four D3CMCXXX ACPI configurations achieved by `PPR Unit=2` also require setting `Device0` for the GMSL2 **aggregated-link** deserializer I2C address, for example `MAX9296A`, and `Device2` for the sensor I2C address, for example `ISX031`.

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **oToCAM222**
   <!--hide_directive:sync: otocam222hide_directive-->

   Below is an ACPI device configuration example for [oToBrite oToCAM222](https://www.otobrite.com/product/automotive-camera/isx021_gmsl2_otocam222-s195m) GMSL2 camera modules:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
   | ------------------- | ---------- | ---------- | ---------- | ---------- |
   | GMSL Camera suffix  | a          | g          | e          | k          |
   | Custom HID          | `OTOC1021` | `OTOC1021` | `OTOC1021` | `OTOC1021` |
   | PPR Value           | 2          | 2          | 2          | 2          |
   | PPR Unit            | 1          | 1          | 1          | 1          |
   | Camera module label | `otocam`   | `otocam`   | `otocam`   | `otocam`   |
   | MIPI Port (Index)   | 0          | 0          | 4          | 4          |
   | LaneUsed            | x4         | x4         | x4         | x4         |
   | Number of I2C       | 3          | 3          | 3          | 3          |
   | I2C Channel         | I2C1       | I2C1       | I2C0       | I2C0       |
   | Device0 I2C Address | 10         | 11         | 10         | 11         |
   | Device1 I2C Address | 18         | 19         | 18         | 19         |
   | Device2 I2C Address | 48         | 48         | 48         | 48         |

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **oToCAM223**
   <!--hide_directive:sync: otocam223hide_directive-->

   Below is an ACPI device configuration example for [oToBrite oToCAM223](https://www.otobrite.com/product/automotive-camera/isx031_gmsl2_otocam223-s195m) GMSL2 camera modules:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
   | ------------------- | ---------- | ---------- | ---------- | ---------- |
   | GMSL Camera suffix  | a          | g          | e          | k          |
   | Custom HID          | `OTOC1031` | `OTOC1031` | `OTOC1031` | `OTOC1031` |
   | PPR Value           | 2          | 2          | 2          | 2          |
   | PPR Unit            | 1          | 1          | 1          | 1          |
   | Camera module label | `otocam`   | `otocam`   | `otocam`   | `otocam`   |
   | MIPI Port (Index)   | 0          | 0          | 4          | 4          |
   | LaneUsed            | x4         | x4         | x4         | x4         |
   | Number of I2C       | 3          | 3          | 3          | 3          |
   | I2C Channel         | I2C1       | I2C1       | I2C0       | I2C0       |
   | Device0 I2C Address | 10         | 11         | 10         | 11         |
   | Device1 I2C Address | 18         | 19         | 18         | 19         |
   | Device2 I2C Address | 48         | 48         | 48         | 48         |

   <!--hide_directive:::
   ::::hide_directive-->

   > **Note:** GMSL2 _aggregated-link_ `SerDes` CSI-2 ports 0 and 4 are purposely set to `LaneUsed = x4` to improve Intel® IPU6 DPHY signal-integrity issues on the [SEAVO® Embedded Computer HB03](https://www.seavo.com/en/products/products-info_itemid_693.html).

   ![SEAVO HB03 layout](../../images/gmsl/gmsl-seavo-hb03.png)

   > **Attention:** For the time being, each GMSL2 **aggregated-link** deserializer, for example `MAX9296A`, on the same I2C channel must set an identical _Custom HID_ and _Camera module label_ tuple matching the GMSL2 serializer and camera sensor device type.
   >
   > For the [SEAVO® Embedded Computer HB03](https://www.seavo.com/en/products/products-info_itemid_693.html) Add-in-Card (AIC), the I2C1-channel **aggregated-link** deserializer at I2C device `0x48` can set the _Custom HID_, for example `INTC10CD`, and _Camera module label_, for example `d4xx`, tuple for both GMSL camera suffixes `a` and `g`, while the other **aggregated-link** deserializer at I2C device `0x4a` can use a different _Custom HID_, for example `INTC1031`, and _Camera module label_, for example `isx031`, tuple on GMSL camera suffixes `e` and `k`.

   <!--hide_directive:::::
   :::::{tab-item}hide_directive--> **Axiomtek® ROBOX500**

   The [Axiomtek® ROBOX500](https://www.axiomtek.com/ROBOX500/) may provide either 4x GMSL or 8x GMSL camera interfaces (FAKRA universal type).

   <!--hide_directive::::{tab-set}
   :::{tab-item}hide_directive--> **RealSense™ D457**
   <!--hide_directive:sync: realsensehide_directive-->

   Below is an ACPI device configuration example for 4x Intel® RealSense Depth Camera D457 GMSL2 modules:

   _**Standalone-link** `SerDes` CSI-2 port 0, 1, 2 and 3 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
   | ------------------- | ---------- | ---------- | ---------- | ---------- |
   | Camera suffix       | a          | b          | c          | d          |
   | Custom HID          | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` |
   | PPR Value           | 2          | 2          | 2          | 2          |
   | PPR Unit            | 1          | 1          | 1          | 1          |
   | Camera module label | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     |
   | MIPI Port (Index)   | 0          | 1          | 2          | 3          |
   | LaneUsed            | x2         | x2         | x2         | x2         |
   | Number of I2C       | 3          | 3          | 3          | 3          |
   | I2C Channel         | I2C5       | I2C5       | I2C5       | I2C5       |
   | Device0 I2C Address | 12         | 14         | 16         | 18         |
   | Device1 I2C Address | 42         | 44         | 62         | 64         |
   | Device2 I2C Address | 48         | 4a         | 68         | 6c         |

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **D3CMCXXX-115-084**
   <!--hide_directive:sync: d3cmc115hide_directive-->

   Below is an ACPI device configuration example for four GMSL2 camera modules from [D3 Embedded Discovery](https://www.d3embedded.com/product/isx031-smart-camera-narrow-fov-gmsl2-unsealed/):

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1           | Camera 2           | Camera 3           | Camera 4           |
   | ------------------- | ------------------ | ------------------ | ------------------ | ------------------ |
   | Camera suffix       | a                  | b                  | c                  | d                  |
   | Custom HID          | `D3000004`         | `D3000004`         | `D3000004`         | `D3000004`         |
   | PPR Value           | 2                  | 2                  | 2                  | 2                  |
   | PPR Unit            | 1                  | 1                  | 1                  | 1                  |
   | Camera module label | `D3CMCXXX-115-084` | `D3CMCXXX-115-084` | `D3CMCXXX-115-084` | `D3CMCXXX-115-084` |
   | MIPI Port (Index)   | 0                  | 1                  | 2                  | 3                  |
   | LaneUsed            | x2                 | x2                 | x2                 | x2                 |
   | Number of I2C       | 3                  | 3                  | 3                  | 3                  |
   | I2C Channel         | I2C5               | I2C5               | I2C5               | I2C5               |
   | Device0 I2C Address | 48                 | 4a                 | 68                 | 6c                 |
   | Device1 I2C Address | 42                 | 44                 | 62                 | 64                 |
   | Device2 I2C Address | 12                 | 14                 | 16                 | 18                 |

   > **Note:** On Axiomtek ROBOX500, the 4x D3CMCXXX camera ACPI configuration achieved by `PPR Unit=1` requires setting `Device0` for the GMSL2 **aggregated-link** deserializer I2C address, for example `MAX9296A`, and `Device2` for the sensor I2C address, for example `ISX031`.

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **D3CMCXXX-106-084**
   <!--hide_directive:sync: d3cmc106hide_directive-->

   Below is an ACPI device configuration example for four GMSL2 camera modules from [D3 Embedded Discovery PRO](https://www.d3embedded.com/product/imx390-medium-fov-gmsl2-sealed/):

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1           | Camera 2           | Camera 3           | Camera 4           |
   | ------------------- | ------------------ | ------------------ | ------------------ | ------------------ |
   | Camera suffix       | a                  | b                  | c                  | d                  |
   | Custom HID          | `D3000005`         | `D3000005`         | `D3000005`         | `D3000005`         |
   | PPR Value           | 2                  | 2                  | 2                  | 2                  |
   | PPR Unit            | 1                  | 1                  | 1                  | 1                  |
   | Camera module label | `D3CMCXXX-106-084` | `D3CMCXXX-106-084` | `D3CMCXXX-106-084` | `D3CMCXXX-106-084` |
   | MIPI Port (Index)   | 0                  | 1                  | 2                  | 3                  |
   | LaneUsed            | x2                 | x2                 | x2                 | x2                 |
   | Number of I2C       | 3                  | 3                  | 3                  | 3                  |
   | I2C Channel         | I2C5               | I2C5               | I2C5               | I2C5               |
   | Device0 I2C Address | 48                 | 4a                 | 68                 | 6c                 |
   | Device1 I2C Address | 42                 | 44                 | 62                 | 64                 |
   | Device2 I2C Address | 12                 | 14                 | 16                 | 18                 |

   > **Note:** The D3CMCXXX ACPI configuration with `PPR Unit=2` requires setting `Device0` for the GMSL2 **aggregated-link** deserializer I2C address, for example `MAX9296A`, and `Device2` for the sensor I2C address, for example `ISX031`.

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **oToCAM222**
   <!--hide_directive:sync: otocam222hide_directive-->

   Below is an ACPI device configuration example for [oToBrite oToCAM222](https://www.otobrite.com/product/automotive-camera/isx021_gmsl2_otocam222-s195m) GMSL2 camera modules:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
   | ------------------- | ---------- | ---------- | ---------- | ---------- |
   | GMSL Camera suffix  | a          | b          | c          | d          |
   | Custom HID          | `OTOC1021` | `OTOC1021` | `OTOC1021` | `OTOC1021` |
   | PPR Value           | 2          | 2          | 2          | 2          |
   | PPR Unit            | 1          | 1          | 1          | 1          |
   | Camera module label | `otocam`   | `otocam`   | `otocam`   | `otocam`   |
   | MIPI Port (Index)   | 0          | 1          | 2          | 3          |
   | LaneUsed            | x2         | x2         | x2         | x2         |
   | Number of I2C       | 3          | 3          | 3          | 3          |
   | I2C Channel         | I2C5       | I2C5       | I2C5       | I2C5       |
   | Device0 I2C Address | 10         | 11         | 10         | 11         |
   | Device1 I2C Address | 18         | 19         | 18         | 19         |
   | Device2 I2C Address | 48         | 4a         | 68         | 6c         |

   <!--hide_directive:::
   :::{tab-item}hide_directive--> **oToCAM223**
   <!--hide_directive:sync: otocam223hide_directive-->

   Below is an ACPI device configuration example for [oToBrite oToCAM223](https://www.otobrite.com/product/automotive-camera/isx031_gmsl2_otocam223-s195m) GMSL2 camera modules:

   _**Aggregated-link** `SerDes` CSI-2 port 0 and 4 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor  | Camera 1   | Camera 2   | Camera 3   | Camera 4   |
   | ------------------- | ---------- | ---------- | ---------- | ---------- |
   | GMSL Camera suffix  | a          | b          | c          | d          |
   | Custom HID          | `OTOC1031` | `OTOC1031` | `OTOC1031` | `OTOC1031` |
   | PPR Value           | 2          | 2          | 2          | 2          |
   | PPR Unit            | 1          | 1          | 1          | 1          |
   | Camera module label | `otocam`   | `otocam`   | `otocam`   | `otocam`   |
   | MIPI Port (Index)   | 0          | 1          | 2          | 3          |
   | LaneUsed            | x2         | x2         | x2         | x2         |
   | Number of I2C       | 3          | 3          | 3          | 3          |
   | I2C Channel         | I2C5       | I2C5       | I2C5       | I2C5       |
   | Device0 I2C Address | 10         | 11         | 10         | 11         |
   | Device1 I2C Address | 18         | 19         | 18         | 19         |
   | Device2 I2C Address | 48         | 4a         | 68         | 6c         |

   <!--hide_directive:::
   ::::hide_directive-->

   ![Axiomtek ROBOX500](../../images/gmsl/gmsl2-robox500.jpg "axiomtek robox500")

   Another example below illustrates how to configure ACPI devices for 8x Intel® RealSense Depth Camera D457 GMSL2 modules:

   ![Axiomtek ROBOX500 8x layout](../../images/gmsl/gmsl2-robox500-x8.png "axiomtek robox500 x8 layout")

   _**Aggregated-link** `SerDes` CSI-2 port 0, 1, 2 and 3 and I2C settings for GMSL Add-in-Card (AIC)_

   | UEFI Custom Sensor     | Camera 1   | Camera 2   | Camera 3   | Camera 4   | N/A        | N/A        | N/A        | N/A        |
   | ---------------------- | ---------- | ---------- | ---------- | ---------- | ---------- | ---------- | ---------- | ---------- |
   | Camera suffix (letter) | a          | b          | c          | d          | _g_        | _h_        | _i_        | _j_        |
   | Custom HID             | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` | `INTC10CD` |
   | PPR Value              | 2          | 2          | 2          | 2          | 2          | 2          | 2          | 2          |
   | PPR Unit               | 1          | 1          | 1          | 1          | 1          | 1          | 1          | 1          |
   | Camera module label    | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     | `d4xx`     |
   | MIPI Port (Index)      | 0          | 1          | 2          | 3          | 0          | 1          | 2          | 3          |
   | LaneUsed               | x2         | x2         | x2         | x2         | x2         | x2         | x2         | x2         |
   | Number of I2C          | 3          | 3          | 3          | 3          | 3          | 3          | 3          | 3          |
   | I2C Channel            | I2C5       | I2C5       | I2C5       | I2C5       | _I2C5_     | _I2C5_     | _I2C5_     | _I2C5_     |
   | Device0 I2C Address    | 12         | 14         | 16         | 18         | _13_       | _15_       | _17_       | _19_       |
   | Device1 I2C Address    | 42         | 44         | 62         | 64         | _43_       | _45_       | _63_       | _65_       |
   | Device2 I2C Address    | 48         | 4a         | 68         | 6c         | _48_       | _4a_       | _68_       | _6c_       |

   <!--hide_directive:::::
   ::::::hide_directive-->
