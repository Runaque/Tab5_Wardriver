# Tab5_Wardriver
A wardriving platform build upon the M5Stack Tab5 development board.


<img width="1280" height="720" alt="bootscreen" src="https://github.com/user-attachments/assets/cbfb8bbb-e3c3-4d5c-832e-9722a2a5ffcd" />




This project started with a simple question: what can the brand new M5Stack Tab5 actually do beyond its official documentation?

The Tab5 is a powerful ESP32-P4 + ESP32-C6 based tablet with a 5-inch touchscreen, built-in WiFi, camera, microphone, SD card slot, and a removable NP-F series battery. It was released in early 2026 and at the time of this project, had almost no community knowledge base, minimal documentation, and several undiscovered firmware bugs.

Rather than waiting for the ecosystem to mature, I decided to build something real with it, a fully self-contained GPS-enabled wardriving platform. What followed was three weeks of pioneering development on undocumented hardware, filing multiple firmware bug reports to M5Stack's GitHub, reverse-engineering pin mappings, and eventually producing a complete custom device that outperforms dedicated wardriving hardware in head-to-head testing.

## So, what is Wardriving?

Originally it was the act of trying to find vulnerable and open networks to exploit by hackers to hide who they are and where they are from leaving their tracks at the doorstep of the unknowingly owners of that vulnerable or open network. This practice still exists, but happens far less than before with new technologies that arose that helped masking your location from your location. VPNs and proxies changed the game.

Wardriving today is mostly the practice of passively scanning for WiFi access points while moving through an area, recording their MAC addresses, SSIDs, encryption types, signal strengths, and GPS coordinates. The collected data is uploaded to community databases like WiGLE (Wireless Geographic Logging Engine), contributing to a global map of wireless network coverage. It's a bit the "hackers form" of Pokémon Go.

I usually upload my Wardrive logs (Tab5 and WiGLE app) once or twice a week to WiGLE.net and this translates to an upload page looking like this.


<img width="1280" height="714" alt="image" src="https://github.com/user-attachments/assets/7c79687c-a7c4-4339-a05a-410ef7856988" />


My personal stats are currently (July 9th 2026) looking as shown below.


<img width="1890" height="400" alt="image" src="https://github.com/user-attachments/assets/e4288ab2-6b28-4369-96b3-13190353d173" />


While Wardrivings seems utterly useless to most people, it might stimulate you to have a healthy walk or look for places you have never been before! While the used device (Tab5 Wardriver, a JustCallMeKoko based ESP32 Marauder or another device) is exploring what APs are broadcasting around you, you might be seeing places you have never been before, perhaps even discover places you might be willing to come back again.

Wardriving is **passive and legal** in my country, although it is kind of a grey area, (note: local laws could tell otherwise, please do your own due diligence before practicing it), the device only listens, never connects or interacts with networks. It is used by security researchers, network engineers, and hobbyists to understand wireless coverage, study encryption adoption trends, and contribute to open data initiatives.

## Hardware

**Core Components**

- **M5Stack Tab5 Kit** — ESP32-P4 (main processor) + ESP32-C6 (WiFi/BT radio), 5" 1280x720 touchscreen, NP-F550 2000mAh 7.4V battery included
- **M5Stack GPS SMA Unit** — AT6668 GNSS module (GPS + BDS + GLONASS), connected via Grove PORT.A at 115200 baud
- **External SMA Antenna** — swappable between a compact stick antenna (walking) and a flat magnetic patch antenna (car roof mounting)
- **Hot-glue Gun** — Just a cheap hot-glue gun is fine
- **MicroSD Card** — PNY 32GB, FAT32 formatted, for field data logging (Optional on the current build)

**Custom Enclosure**

This is probably the part that takes most of the time if you 3d print it yourself. On my Creality Ender 3 S1 it took about 4 hours to print with settings dialed in to have a high quality enclosure once you pop it of the printing bed. I chose to go for the most rigid settings and went for a 100% infill with the only downside the added weight.


<img width="1173" height="595" alt="image" src="https://github.com/user-attachments/assets/d48cf544-031b-4c02-87d7-fb13da23cfab" />


- **3D printed white back cover** — redesigned in TinkerCAD, printed on a Creality Ender 3 S1 in Polymaker Panchroma Satin White. My model is a remix of the cover I found on Thingiverse and is named "M5Stack TAB5 Basic Case, by daffniles is licensed under the Creative Commons - Attribution - Share Alike license." So knowing this, I license the remix under the same license of the original maker!
- **2mm Grove cable routing slot** — allows the GPS module cable to route cleanly back into the enclosure
- **External SMA connector passthrough** — antenna swappable without opening the device
- **Ubiquiti switch rack screws (shortened with a Dremel)** — mount the cover to the Tab5's M3 holes, exposed heads provide an industrial aesthetic and act as protective feet
- **"Big Haul" variant model** — extended back cover design to accommodate larger NP-F series batteries (NP-F750/NP-F970) for all-day sessions is also available through this project as from today (June 23rd)


<img width="1126" height="691" alt="image" src="https://github.com/user-attachments/assets/7fb3c4c3-fd0d-470d-bc06-34b76a87ed8b" />

You can download this custom enclosure on my Printables page by hitting the download button below.

<a href="https://www.printables.com/model/1777519-m5stack-tab5-cover-for-use-with-external-gps-anten">
  <img src="https://github.com/Runaque/Random_dumps/blob/main/Download_350.png?raw=true" alt="M5Stack Tab5 Cover" width="350" />
</a>

## The Build

The build is actually fairly easy! Remove the nut and washer from the GPS module (we don't need them anymore), connect the Grove cable already to the GPS module, fit the SMA connector through the cutout in the 3D printed case and temporarily lock it in place with the nut on the outside. With the glue-gun heated, we are going to fix the GPS module to the 3D printed enclosure by applying plenty of glue around the unit (see image below), and let it cool down (fun fact: I used the refrigerator to speed up the process).

<img width="1280" height="578" alt="image" src="https://github.com/user-attachments/assets/b2aaa0e6-11ae-41e5-be1c-c49592e8116d" />

Connect the other end of the Grove cable to the Tab5's PORT.A and tuck the cable through the small slot in the 3D printed cover, forming a small loop on the outside as strain relief (as seen in the photo below).

<img width="1280" height="578" alt="image" src="https://github.com/user-attachments/assets/01810d85-33fa-40e5-a365-57791bffd639" />

Mount the cover with the screws or bolts of your choice. For myself, I went for the Ubiquiti screws that also function as sort of a stand when the device is flat on its back (and protect it from scratching).
Now you can remove the nut from the SMA connector since your antenna is going to be using the whole SMA connector.

## Power

The Tab5 Kit includes an NP-F550 battery (7.4V, 2000mAh) that clips to the back of the device. Running at 7.4V vs USB's 5V provides significantly more RF power to the ESP32-C6 WiFi radio, resulting in dramatically better scanning performance. Field tests confirmed the battery-powered device finds 15+ networks on the first scan, while USB power finds significantly fewer due to power budget throttling.

## Software

**Platform**

- UIFlow2 v2.4.5 — MicroPython v1.27.0 on ESP32-P4
- Language: MicroPython

**Key Features**

- **WiFi scanning** — every 15 seconds via ESP32-C6
- **GPS NMEA parser** — reads $GNRMC and $GNGGA sentences at 115200 baud, extracts latitude, longitude, altitude, and satellite count
- **GPS-fix-only logging** — networks are only written to the log when a valid GPS fix is confirmed (4+ satellites), ensuring every entry has real coordinates
Satellite count display with colour coding (grey/red/yellow/green)
- **WiGLE native CSV format** — files are directly uploadable to WiGLE with device recognition as `brand=Runaque`
- **Auto-save on STOP & Confirm** — log is saved in flash as `Tab5_Wardriver_xxx.csv` on session end
-  **Sequential file naming** — multiple sessions on one SD card without overwriting
- **POI waypoint logging** — tap to save a GPS waypoint to a GPX file (in case you found a nice place you want to take your wife out for dinner)
- **Boot screen** — custom skull/antenna logo with Watch Dogs font easter egg
- **Ring buffer display** — 200 device rolling buffer, 15 visible rows

**WiGLE File Format**

<img width="1038" height="56" alt="image" src="https://github.com/user-attachments/assets/5c437cc5-67f8-4c7a-88bf-4e6e54864862" />

## Firmware Challenges & Bug Reports

Building on brand new hardware meant encountering undiscovered bugs. During development, three firmware issues were identified and reported to M5Stack's GitHub:

**Issue #94 — Fatal crash on WiFi scan (RESOLVED ✅)**

The device crashed with `MEPC: 0x4ff13582` on every `sta.scan()` call. This was fixed in UIFlow2 v2.4.5 + ESP32-C6 firmware v2.12.6.

**Issue #94 (ongoing) — SD card + WiFi SDIO conflict**

After a WiFi scan, mounting the SD card in SDIO mode causes a system crash when WiFi is reactivated. The workaround implemented: WiFi is deactivated before SD card mount, data is saved, then WiFi is reactivated — which causes a controlled reboot. Data is safely written before the crash occurs. M5Stack contributor Felix (felmue) confirmed the conflict is at the software/driver level, not GPIO level, and is investigating.

**Issue #95 — Camera API missing**

The Tab5 has a built-in 2MP SC2356 camera, but the current firmware has no API to access it. The PrtSc button in the UI is a placeholder for when this functionality has been added.

**Issue #96 — USB Host support missing**

The Tab5 has a USB-A port but the current firmware does not support USB Host mode for external devices.

## Performance Results

**Head-to-Head vs ESP32 Marauder V6.1**

Both devices were placed on the passenger seat of a car for a 50-minute drive under identical conditions:

| Device | Networks Found | Duration |

|--------|---------------|----------|

| Tab5 Wardriver | 1,333 | 50 min |

| ESP32 Marauder V6.1 | 881 | 50 min |

**Tab5 Wardriver found 51% more networks** than my ESP32 Marauder V6.1 (JustCallMeKoko firmware 1.12.1) hardware with both the same runtime and exposure to the sky (passenger seat).

**Field Tests**

- School run (30 min, walking): ~826 networks
- Antwerp city center (80 min, walking): 4, 092 networks
- IKEA drive (50 min, car): data with full GPS coordinates logged
  
I also concluded that the Tab5 performs significantly better when running on its NP-F550 battery (7.4V) rather than being powered via USB (5V). The higher voltage delivers full RF power to the ESP32-C6 WiFi radio, resulting in noticeably more networks found from the very first scan.

## Version History

**v1.0** : Stable WiFi scanning, flash logging, USB retrieval

**v1.1** : PrtSc button placeholder

**v1.2** : POI button, GPS coordinate placeholders

**v1.3** : Boot screen splash

**v1.3.1** : SD card auto-save, Tab5_Wardriver_xxx.csv naming

**v1.4** : GPS NMEA parser, AT6668 integration, real coordinates

**v1.4.1** : GPS-fix-only logging, satellite count display

**v1.4.2** : WiGLE native format, frequency calculation, formatted timestamps

**v1.4.3-RC1** : State machine architecture (IDLE → SCANNING → STOPPING → EXPORTING)

**v1.4.4-RC1** : SDIO conflict isolation attempts

**v1.4.4-RC1B** : SPI SD mode exploration (failed)

**v1.4.4-RC1C** : v1.4.2 SD pattern + GPS dual-fix logic (RMC + GGA)

**v1.4.5-RC1** : Version refinement (RC1C codebase)

**v1.4.6-RC1** : Flash-only export, WiGLE CSV perfected, GPS fix logic finalized, SDIO abandoned

**v1.4.7-RC1** : Double-tap STOP confirmation, brightness control with persistence, automatic session separation, session timer reset

**So... What's next?**

- **PrtSc button** — currently the button visible is a placeholder awaiting for M5Stack camera API implementation
- **SD card SPI mode** — Awaiting M5Stack conflict resolvement
- **WiGLE direct upload** — direct upload from device to WiGLE

## ⚠️ INSTALLATION WARNING: UIFlow Web Editor Clipboard Truncation

Do **NOT** copy-paste code directly into the UIFlow web text editor if your script *exceeds ~500 lines. The web editor has a silent clipboard buffer limit that will truncate your code without warning, leaving your device with incomplete/broken code.*

**SAFE METHOD:**

1. Save the provided code in this project as "main.py" in a text editor

2. Use WebTerminal

<img width="783" height="493" alt="image" src="https://github.com/user-attachments/assets/7e593d5c-1f30-4262-b8b4-ebab94349d28" />

3. Connect Tab5 via USB and connect the device by selecting the right serial port (COM)

4. To access the flash of the device, click "File", then open "flash"

<img width="899" height="481" alt="image" src="https://github.com/user-attachments/assets/3990a239-78e5-485c-b769-7f6e062d6485" />

5. Click on "Delete" to remove the original "main.py" and confirm after this with another click on "Delete"

<img width="916" height="493" alt="image" src="https://github.com/user-attachments/assets/e8fa03a1-7737-4f2e-98ed-81664e423ab0" />

6. To bypass the web editor for the MicroPyton code, click on "Send File to Here" and then select the provided code in the file you renamed in step 1. Do the same thing with the "bootscreen.jpg" to have the Tab5 Wardriver bootscreen when powering up your device

<img width="879" height="476" alt="image" src="https://github.com/user-attachments/assets/2e8e805c-a000-492d-8d9b-0c0d15b817ba" />

7. This bypasses the web editor entirely and ensures 100% of code is transferred

## PhotoBombs

<img width="1280" height="578" alt="image" src="https://github.com/user-attachments/assets/d06a920f-379d-4a5c-9607-6b4642db3d17" />

<img width="1280" height="577" alt="image" src="https://github.com/user-attachments/assets/10c59704-80fb-4a8d-89db-9c55ff3e8034" />

<img width="1280" height="578" alt="image" src="https://github.com/user-attachments/assets/d4e8fe0d-49a7-438c-b0c1-98045969bfd7" />

<img width="1280" height="578" alt="image" src="https://github.com/user-attachments/assets/c39a71b2-b56e-46e8-9c7a-067e3baf4627" />

<img width="1280" height="578" alt="image" src="https://github.com/user-attachments/assets/252f8645-1547-4b1d-87c9-7f584ed72050" />

<img width="1280" height="578" alt="image" src="https://github.com/user-attachments/assets/c59e220b-d419-4734-94c2-1f1c17ec373a" />

## Support

If you found this project interesting and helpful, consider [buying me a coffee](https://buymeacoffee.com/runaque)!


<a href="https://buymeacoffee.com/runaque" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" >
</a>
