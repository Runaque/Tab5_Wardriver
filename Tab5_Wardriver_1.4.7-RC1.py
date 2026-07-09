# Tab5 Wardriver v1.4.7
# GPS fix + flash-only logging (SDIO driver broken - USB retrieval workaround)
# UIFlow2 2.4.5 MicroPython
# Permanent wardriving app for M5Stack Tab5
# Flash accumulation with 9.5MB size limit
# Sequential file naming: Tab5_Wardriver_001.csv
# GPS integration — AT6668 via Grove PORT.A (G53/G54)
# GPS-fix-only logging — no zero coordinate entries
# Satellite count display with colour coding
# POI waypoint logging to GPX
# Boot screen splash
# Double-tap STOP confirmation (accidental stop prevention)
# Brightness control with +/- buttons (vertically stacked)
# Auto-clear wardrive_current.csv after session save (session separation)
# Session timer resets on STOP
#
# Licensed under the Apache License 2.0
# See LICENSE file for details
# https://www.apache.org/licenses/LICENSE-2.0
#
# Build in Antwerp by Runaque
#
# A healthy Wardriving session starts with a healthy breakfast
# Don't forget to pack healthy a snack and some water for a long lengthy Wardriving session

import os, gc, utime, network
import M5
from M5 import *
import m5ui
import lvgl as lv
from machine import UART, Pin

# ─── Config ───────────────────────────────────────────────────────────────────
SCAN_INTERVAL_MS   = 15000
HEADER_INTERVAL_MS = 1000
GPS_INTERVAL_MS    = 500
FLUSH_INTERVAL     = 20
MAX_VISIBLE_ROWS   = 15
MAX_DEVICES        = 200
FLASH_LOG          = "/flash/wardrive_current.csv"
SD_LOG_PREFIX      = "Tab5_Wardriver_"
MAX_LOG_BYTES      = 9 * 1024 * 1024 + 512 * 1024  # 9.5 MB

# GPS UART — PORT.A = G53 (TX) / G54 (RX)
GPS_TX_PIN = 53
GPS_RX_PIN = 54
GPS_BAUD   = 115200

SEC = {0:"OPEN", 1:"WEP", 2:"WPA", 3:"WPA2", 4:"WPA/2",
       5:"WPA3", 6:"WPA2/3", 7:"WAPI", 8:"OWE"}

# ─── System State Machine ─────────────────────────────────────────────────────
STATE_IDLE = 0
STATE_SCANNING = 1
STATE_STOPPING = 2
STATE_EXPORTING = 3

system_state = STATE_IDLE

# ─── State ────────────────────────────────────────────────────────────────────
scanning      = False
session_start = None
wifi_count    = 0
csv_file      = None
pending_flush = 0
last_scan     = 0
last_header   = 0
last_gps      = 0
log_full      = False
gps_uart      = None

# Confirmation state
confirm_mode = False
confirm_timeout = 0

# Brightness control
brightness_level = 100

# Ring buffer
devices     = [None] * MAX_DEVICES
write_index = 0
seen_macs   = set()

# GPS state
gps_lat   = None
gps_lon   = None
gps_alt   = None
gps_fix   = False
gps_sats  = 0
poi_count = 0

# ─── UI handles ───────────────────────────────────────────────────────────────
page0        = None
page_confirm = None
lbl_wifi     = None
lbl_timer    = None
lbl_status   = None
lbl_size     = None
lbl_gps      = None
lbl_sats     = None
lbl_brightness = None
btn_scan     = None
btn_prtsc    = None
btn_poi      = None
btn_clear    = None
btn_brightness_up = None
btn_brightness_down = None
btn_yes      = None
btn_no       = None
rows         = []

# ─── Helpers ──────────────────────────────────────────────────────────────────

def enc_str(enc):
    return SEC.get(enc, "UNK")

def fmt_mac(b):
    if isinstance(b, (bytes, bytearray)):
        return ":".join("{:02X}".format(x) for x in b)
    return str(b)

def elapsed():
    if session_start is None:
        return "00:00:00"
    s = utime.time() - session_start
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)

def safe_ssid(v):
    try:
        s = v.decode("utf-8", "ignore") if isinstance(v, bytes) else str(v)
        s = s.replace(",", " ").replace("\n", " ").replace("\r", " ")
        return s if s else "<hidden>"
    except Exception:
        return "<invalid>"

def fmt_size(b):
    if b < 1024:
        return "{}B".format(b)
    elif b < 1024 * 1024:
        return "{:.1f}KB".format(b / 1024)
    else:
        return "{:.2f}MB".format(b / (1024 * 1024))

def wifi_on():
    """Enable WiFi interface."""
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    utime.sleep_ms(200)

def wifi_off():
    """Disable WiFi interface with proper SDIO release timing."""
    sta = network.WLAN(network.STA_IF)
    try:
        sta.disconnect()
    except:
        pass
    utime.sleep_ms(200)
    sta.active(False)
    utime.sleep_ms(1500)  # Allow SDIO bus to fully release

def set_status(msg, color=0x8B949E):
    if lbl_status is None:
        return
    lbl_status.set_text(msg)
    lbl_status.set_style_text_color(
        lv.color_hex(color), lv.PART.MAIN | lv.STATE.DEFAULT)

def update_size_label():
    if lbl_size is None:
        return
    size  = get_log_size()
    pct   = int(size * 100 / MAX_LOG_BYTES)
    color = 0x3FB950 if pct < 70 else 0xD29922 if pct < 90 else 0xF85149
    lbl_size.set_text("Log: {} / {}%".format(fmt_size(size), pct))
    lbl_size.set_style_text_color(
        lv.color_hex(color), lv.PART.MAIN | lv.STATE.DEFAULT)

def update_gps_label():
    if lbl_gps is None or lbl_sats is None:
        return
    if gps_fix:
        lbl_gps.set_text("Lat: {:.5f} / Lon: {:.5f}".format(gps_lat, gps_lon))
        lbl_gps.set_style_text_color(
            lv.color_hex(0x3FB950), lv.PART.MAIN | lv.STATE.DEFAULT)
    else:
        lbl_gps.set_text("Lat: -- / Lon: --")
        lbl_gps.set_style_text_color(
            lv.color_hex(0x8B949E), lv.PART.MAIN | lv.STATE.DEFAULT)
    # Satellite count colour coding
    if gps_sats == 0:
        sat_color = 0x8B949E   # grey — no satellites
    elif gps_sats < 4:
        sat_color = 0xF85149   # red — poor fix
    elif gps_sats < 6:
        sat_color = 0xD29922   # yellow — marginal fix
    else:
        sat_color = 0x3FB950   # green — good fix
    lbl_sats.set_text("Sats: {}".format(gps_sats))
    lbl_sats.set_style_text_color(
        lv.color_hex(sat_color), lv.PART.MAIN | lv.STATE.DEFAULT)

def load_brightness():
    global brightness_level
    try:
        with open("/flash/brightness.txt", "r") as f:
            brightness_level = int(f.read().strip())
    except Exception:
        brightness_level = 100
    set_brightness(brightness_level)

def save_brightness():
    try:
        with open("/flash/brightness.txt", "w") as f:
            f.write(str(brightness_level))
    except Exception:
        pass

def set_brightness(level):
    global brightness_level
    brightness_level = max(20, min(100, level))  # Clamp 20-100%
    try:
        M5.Lcd.setBrightness(brightness_level)
    except Exception:
        pass
    if lbl_brightness is not None:
        lbl_brightness.set_text("Bright: {}%".format(brightness_level))

# ─── Flash save (numbered files in flash, no SD) ────────────────────────────────

def save_to_flash():
    """Save current log to numbered file in flash with WiGLE header."""
    try:
        size = get_log_size()
        if size == 0:
            set_status("Nothing to save.", 0xD29922)
            return False

        # Find next available numbered filename in flash
        try:
            existing = os.listdir('/flash')
        except:
            existing = []
        
        highest = 0
        for f in existing:
            if f.startswith(SD_LOG_PREFIX) and f.endswith('.csv'):
                try:
                    num = int(f[len(SD_LOG_PREFIX):f.index('.csv')])
                    if num > highest:
                        highest = num
                except Exception:
                    pass
        
        new_filename = "/flash/{}{:03d}.csv".format(SD_LOG_PREFIX, highest + 1)

        # Copy current file to numbered file (both in flash)
        with open(FLASH_LOG, 'r') as src:
            content = src.read()
        
        # Ensure header block is present perfectly in the numbered file
        if not content.startswith('WigleWifi'):
            content = ("WigleWifi-1.4,appRelease=2.26,model=Tab5_Wardriver,"
                      "release=1.4.7,device=Tab5_Wardriver,display=1280x720,"
                      "board=Tab5,brand=Runaque\n"
                      "MAC,SSID,AuthMode,FirstSeen,Channel,Frequency,"
                      "RSSI,CurrentLatitude,CurrentLongitude,"
                      "AltitudeMeters,AccuracyMeters,Type\n") + content
        
        with open(new_filename, 'w') as dst:
            dst.write(content)

        set_status("Saved: {}".format(new_filename.replace('/flash/', '')), 0x3FB950)
        print("Saved to flash:", new_filename)
        return True

    except Exception as e:
        print("Flash save error:", e)
        set_status("Save failed: {}".format(e), 0xF85149)
        return False

# ─── GPS NMEA parser ──────────────────────────────────────────────────────────

def init_gps():
    global gps_uart
    try:
        gps_uart = UART(1, baudrate=GPS_BAUD,
                        tx=Pin(GPS_TX_PIN), rx=Pin(GPS_RX_PIN))
        print("GPS UART initialised on G{}/G{}".format(GPS_TX_PIN, GPS_RX_PIN))
    except Exception as e:
        print("GPS init error:", e)
        gps_uart = None

def nmea_checksum(sentence):
    """Verify NMEA checksum."""
    try:
        if '*' not in sentence:
            return True  # No checksum to verify
        data, chk = sentence.rsplit('*', 1)
        calc = 0
        for c in data[1:]:  # Skip the $ sign
            calc ^= ord(c)
        return calc == int(chk.strip(), 16)
    except Exception:
        return False

def parse_lat(val, hemi):
    """Convert NMEA lat to decimal degrees."""
    try:
        deg = float(val[:2])
        mins = float(val[2:])
        result = deg + mins / 60.0
        if hemi == 'S':
            result = -result
        return result
    except Exception:
        return None

def parse_lon(val, hemi):
    """Convert NMEA lon to decimal degrees."""
    try:
        deg = float(val[:3])
        mins = float(val[3:])
        result = deg + mins / 60.0
        if hemi == 'W':
            result = -result
        return result
    except Exception:
        return None

def parse_nmea(line):
    """Parse NMEA sentence and update GPS state (v1.4.2 proven logic)."""
    global gps_lat, gps_lon, gps_alt, gps_fix, gps_sats
    try:
        line = line.strip()
        if not line.startswith('$'):
            return
        if not nmea_checksum(line):
            return

        # Remove checksum
        if '*' in line:
            line = line[:line.index('*')]

        parts = line.split(',')
        sentence = parts[0]

        # $GNRMC / $GPRMC — Recommended Minimum Navigation Information
        if sentence in ('$GNRMC', '$GPRMC'):
            if len(parts) < 7:
                return
            status = parts[2]  # A=active, V=void
            if status == 'A' and parts[3] and parts[4] and parts[5] and parts[6]:
                lat = parse_lat(parts[3], parts[4])
                lon = parse_lon(parts[5], parts[6])
                if lat is not None and lon is not None:
                    gps_lat = lat
                    gps_lon = lon
                    gps_fix = True  # RMC status 'A' = valid position
                    print(f"GPS FIX (RMC): {gps_sats} sats, {gps_lat:.6f}, {gps_lon:.6f}")
            elif status == 'V':
                gps_fix = False

        # $GNGGA / $GPGGA — Global Positioning System Fix Data (altitude + satellites)
        elif sentence in ('$GNGGA', '$GPGGA'):
            if len(parts) < 10:
                return
            fix_quality = parts[6]
            if fix_quality and fix_quality != '0':
                gps_fix = True  # GGA fix quality > 0 = valid fix
                # Satellites in use
                if parts[7]:
                    try:
                        gps_sats = int(parts[7])
                    except Exception:
                        pass
                # Altitude
                if parts[9]:
                    try:
                        gps_alt = float(parts[9])
                    except Exception:
                        pass
            else:
                gps_fix = False
                gps_sats = 0

    except Exception as e:
        print("NMEA parse error:", e)

def read_gps():
    """Read available NMEA sentences from UART."""
    if gps_uart is None:
        return
    try:
        while gps_uart.any():
            line = gps_uart.readline()
            if line:
                try:
                    parse_nmea(line.decode('ascii', 'ignore'))
                except Exception:
                    pass
    except Exception as e:
        print("GPS read error:", e)

# ─── SD card helpers ──────────────────────────────────────────────────────────

def channel_to_freq(channel):
    """Convert WiFi channel to frequency in MHz."""
    try:
        ch = int(channel)
        if 1 <= ch <= 14:
            return 2407 + (ch * 5)
        elif 36 <= ch <= 165:
            return 5000 + (ch * 5)
        return 2412
    except Exception:
        return 2412

# ─── Flash logging ────────────────────────────────────────────────────────────

def get_log_size():
    try:
        return os.stat(FLASH_LOG)[6]
    except Exception:
        return 0

def clear_log():
    global log_full
    try:
        os.remove(FLASH_LOG)
        log_full = False
        print("Log cleared")
    except Exception:
        pass

def open_log():
    global csv_file, log_full
    try:
        log_full = False
        size = get_log_size()
        if size >= MAX_LOG_BYTES:
            log_full = True
            set_status("Log full! Clear via USB.", 0xF85149)
            return
        file_exists = False
        try:
            os.stat(FLASH_LOG)
            file_exists = True
        except Exception:
            pass
        csv_file = open(FLASH_LOG, "a")
        if not file_exists:
            # Line 1: WiGLE Metadata pre-header
            csv_file.write(
                "WigleWifi-1.4,appRelease=2.26,model=Tab5_Wardriver,"
                "release=1.4.7,device=Tab5_Wardriver,display=1280x720,"
                "board=Tab5,brand=Runaque\n")
            # Line 2: Standard WiGLE structural CSV columns mapping
            csv_file.write(
                "MAC,SSID,AuthMode,FirstSeen,Channel,Frequency,"
                "RSSI,CurrentLatitude,CurrentLongitude,"
                "AltitudeMeters,AccuracyMeters,Type\n")
            csv_file.flush()
        print("Appending to:", FLASH_LOG, "| Size:", fmt_size(size))
        update_size_label()
    except Exception as e:
        print("Log open error:", e)
        csv_file = None

def log_line(d):
    global pending_flush, log_full, scanning, csv_file
    if csv_file is None or log_full:
        return
    # Only log when GPS fix is active
    if not gps_fix:
        return
    try:
        if get_log_size() >= MAX_LOG_BYTES:
            log_full = True
            scanning = False
            csv_file.flush()
            csv_file.close()
            csv_file = None
            set_status("Log full! 9.5MB reached.", 0xF85149)
            btn_scan.set_btn_text("START")
            btn_scan.set_style_bg_color(
                lv.color_hex(0x238636), lv.PART.MAIN | lv.STATE.DEFAULT)
            update_size_label()
            return
        ssid, mac, rssi, chan, enc = d
        
        # Format metrics with correct tracking boundaries
        lat = "{:.8f}".format(gps_lat) if gps_fix and gps_lat is not None else ""
        lon = "{:.8f}".format(gps_lon) if gps_fix and gps_lon is not None else ""
        alt = "{:.1f}".format(gps_alt) if gps_fix and gps_alt is not None else ""
        
        # Call the helper to translate channel directly into a valid MHz value
        freq = channel_to_freq(chan)
        
        # Native alignment tracking matches line-2 header elements column by column
        csv_file.write("{},{},{},{},{},{},{},{},{},{},,WiFi\n".format(
            mac, ssid, enc, utime.time(), chan, freq, rssi, lat, lon, alt))
        
        pending_flush += 1
        if pending_flush >= FLUSH_INTERVAL:
            csv_file.flush()
            pending_flush = 0
            update_size_label()
    except Exception as e:
        print("Write error:", e)

# ─── UI updates ───────────────────────────────────────────────────────────────

def update_header():
    if lbl_wifi is None or lbl_timer is None:
        return
    lbl_wifi.set_text(str(wifi_count))
    lbl_timer.set_text(elapsed())

def refresh_rows():
    idx = write_index - 1
    for row in range(MAX_VISIBLE_ROWS):
        if idx < 0:
            idx = MAX_DEVICES - 1
        d = devices[idx]
        if d is None:
            rows[row].set_text("")
        else:
            ssid, mac, rssi, chan, enc = d
            rows[row].set_text("[W] {}  {}dBm  ch{}  {}".format(
                ssid[:22], rssi, chan, enc))
        idx -= 1

# ─── Button callbacks ─────────────────────────────────────────────────────────

def btn_scan_cb(event_struct):
    global scanning, session_start, csv_file, pending_flush, system_state
    global confirm_mode, confirm_timeout
    
    if event_struct.code != lv.EVENT.CLICKED:
        return
    
    if not scanning:
        # START button pressed
        if log_full:
            set_status("Log full! Clear via USB.", 0xF85149)
            return
        system_state = STATE_SCANNING
        wifi_on()
        scanning = True
        session_start = utime.time()
        open_log()
        if log_full:
            scanning = False
            return
        btn_scan.set_btn_text("STOP")
        btn_scan.set_style_bg_color(
            lv.color_hex(0xDA3633), lv.PART.MAIN | lv.STATE.DEFAULT)
        if gps_fix:
            set_status("Scanning + logging (GPS fix active!)", 0x3FB950)
        else:
            set_status("Scanning... waiting for GPS fix to log", 0xD29922)
    else:
        # STOP button pressed — enter confirmation mode
        if not confirm_mode:
            confirm_mode = True
            confirm_timeout = utime.ticks_ms()
            set_status("TAP STOP AGAIN to confirm (2 sec timeout)", 0xF85149)
            btn_scan.set_btn_text("CONFIRM?")
        else:
            # Second tap — execute stop
            stop_scanning()

def stop_scanning():
    """Execute the actual stop and save."""
    global scanning, session_start, csv_file, pending_flush, confirm_mode, system_state
    
    scanning = False
    confirm_mode = False
    system_state = STATE_IDLE
    session_start = None  # Reset session timer
    
    if csv_file:
        try:
            csv_file.flush()
            csv_file.close()
        except Exception:
            pass
        csv_file = None
        pending_flush = 0
    
    btn_scan.set_btn_text("START")
    btn_scan.set_style_bg_color(
        lv.color_hex(0x238636), lv.PART.MAIN | lv.STATE.DEFAULT)
    update_size_label()
    update_header()  # Update display immediately to show "00:00:00"
    save_to_flash()
    # Clear wardrive_current.csv after successful save for next session separation
    clear_log()
    set_status("Stopped and saved. Ready for next session.", 0x3FB950)

def btn_prtsc_cb(event_struct):
    if event_struct.code != lv.EVENT.CLICKED:
        return
    set_status("Use phone camera for screenshot!", 0x6B4E9B)

def btn_poi_cb(event_struct):
    global poi_count
    if event_struct.code != lv.EVENT.CLICKED:
        return
    try:
        # Read current highest POI number from existing file
        gpx_file = "/flash/wardrive_poi.gpx"
        file_exists = False
        try:
            os.stat(gpx_file)
            file_exists = True
        except Exception:
            pass

        # If file exists, count existing POIs to continue numbering
        if file_exists and poi_count == 0:
            try:
                with open(gpx_file, 'r') as f:
                    content = f.read()
                    poi_count = content.count('<wpt ')
            except Exception:
                pass

        poi_count += 1
        lat  = gps_lat if gps_fix and gps_lat is not None else 0.0
        lon  = gps_lon if gps_fix and gps_lon is not None else 0.0
        alt  = gps_alt if gps_fix and gps_alt is not None else 0.0
        ts   = utime.time()
        name = "POI_{:03d}".format(poi_count)

        # Read existing content, strip closing tag if present, append new wpt
        existing = ""
        if file_exists:
            try:
                with open(gpx_file, 'r') as f:
                    existing = f.read()
                # Remove closing tag if present
                existing = existing.replace('</gpx>', '').strip()
            except Exception:
                pass

        with open(gpx_file, 'w') as f:
            if not existing:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<gpx version="1.1" creator="Tab5 Wardriver v1.4.7">\n')
            else:
                f.write(existing + '\n')
            f.write('  <wpt lat="{}" lon="{}">\n'.format(lat, lon))
            f.write('    <ele>{}</ele>\n'.format(alt))
            f.write('    <name>{}</name>\n'.format(name))
            f.write('    <desc>Timestamp: {}</desc>\n'.format(ts))
            f.write('  </wpt>\n')
            f.write('</gpx>\n')

        if gps_fix:
            set_status("{} saved! {:.5f}, {:.5f}".format(name, lat, lon), 0xD29922)
        else:
            set_status("{} saved! (no GPS fix)".format(name), 0xD29922)
        print("POI saved:", name, lat, lon)

    except Exception as e:
        print("POI error:", e)
        set_status("POI save failed!", 0xF85149)

def btn_clear_cb(event_struct):
    global wifi_count, write_index
    if event_struct.code != lv.EVENT.CLICKED:
        return
    if scanning:
        set_status("Stop scanning first!", 0xF85149)
        return
    wifi_count = 0
    write_index = 0
    seen_macs.clear()
    for i in range(MAX_DEVICES):
        devices[i] = None
    refresh_rows()
    update_header()
    set_status("Display cleared. Log intact.", 0x3FB950)
    gc.collect()

def btn_brightness_up_cb(event_struct):
    global brightness_level
    if event_struct.code != lv.EVENT.CLICKED:
        return
    brightness_level += 10
    set_brightness(brightness_level)
    save_brightness()

def btn_brightness_down_cb(event_struct):
    global brightness_level
    if event_struct.code != lv.EVENT.CLICKED:
        return
    brightness_level -= 10
    set_brightness(brightness_level)
    save_brightness()

def btn_yes_cb(event_struct):
    if event_struct.code != lv.EVENT.CLICKED:
        return
    page0.screen_load()

def btn_no_cb(event_struct):
    if event_struct.code != lv.EVENT.CLICKED:
        return
    page0.screen_load()

# ─── UI construction ──────────────────────────────────────────────────────────

def build_ui():
    global page0, page_confirm, lbl_wifi, lbl_timer, lbl_status, lbl_size, lbl_gps, lbl_sats
    global btn_scan, btn_prtsc, btn_poi, btn_clear, btn_yes, btn_no, rows
    global lbl_brightness, btn_brightness_up, btn_brightness_down

    M5.begin()
    Widgets.setRotation(1)
    m5ui.init()

    page0 = m5ui.M5Page(bg_c=0x000000)

    # Title
    m5ui.M5Label("Tab5 Wardriver v1.4.7", x=12, y=4,
        text_c=0x58A6FF, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_48, parent=page0)

    # WiFi counter
    m5ui.M5Label("WiFi:", x=12, y=62,
        text_c=0x8B949E, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_24, parent=page0)
    lbl_wifi = m5ui.M5Label("0", x=100, y=62,
        text_c=0x3FB950, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_24, parent=page0)

    # Session timer
    m5ui.M5Label("Session:", x=220, y=62,
        text_c=0x8B949E, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_24, parent=page0)
    lbl_timer = m5ui.M5Label("00:00:00", x=390, y=62,
        text_c=0xE6EDF3, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_24, parent=page0)

    # Log size indicator
    lbl_size = m5ui.M5Label("Log: 0B / 0%", x=630, y=62,
        text_c=0x3FB950, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_24, parent=page0)

    # GPS satellites
    lbl_sats = m5ui.M5Label("Sats: --", x=870, y=70,
        text_c=0x8B949E, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_16, parent=page0)

    # GPS coordinates
    lbl_gps = m5ui.M5Label("Lat: -- / Lon: --", x=960, y=70,
        text_c=0x8B949E, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_16, parent=page0)

    # Status line
    lbl_status = m5ui.M5Label("Ready - press START",
        x=10, y=96,
        text_c=0x8B949E, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_16, parent=page0)

    # Pre-allocated fixed rows
    rows = []
    for i in range(MAX_VISIBLE_ROWS):
        lbl = m5ui.M5Label("", x=10, y=118 + (i * 34),
            text_c=0x3FB950, bg_c=0x000000, bg_opa=0,
            font=lv.font_montserrat_16, parent=page0)
        rows.append(lbl)

    # START/STOP button (green)
    btn_scan = m5ui.M5Button(text="START", x=20, y=650,
        w=220, h=52, bg_c=0x238636, text_c=0xFFFFFF,
        font=lv.font_montserrat_24, parent=page0)
    btn_scan.add_event_cb(btn_scan_cb, lv.EVENT.ALL, None)

    # PrtSc button (purple)
    btn_prtsc = m5ui.M5Button(text="PrtSc", x=280, y=650,
        w=200, h=52, bg_c=0x6B4E9B, text_c=0xFFFFFF,
        font=lv.font_montserrat_24, parent=page0)
    btn_prtsc.add_event_cb(btn_prtsc_cb, lv.EVENT.ALL, None)

    # POI button (amber)
    btn_poi = m5ui.M5Button(text="POI", x=520, y=650,
        w=200, h=52, bg_c=0xD29922, text_c=0xFFFFFF,
        font=lv.font_montserrat_24, parent=page0)
    btn_poi.add_event_cb(btn_poi_cb, lv.EVENT.ALL, None)

    # ─── Brightness Control — Vertically Stacked Column (right side) ───────────
    
    # Brightness + button (top)
    btn_brightness_up = m5ui.M5Button(text="+", x=1050, y=520,
        w=210, h=40, bg_c=0x3FB950, text_c=0xFFFFFF,
        font=lv.font_montserrat_20, parent=page0)
    btn_brightness_up.add_event_cb(btn_brightness_up_cb, lv.EVENT.ALL, None)

    # Brightness label (center)
    lbl_brightness = m5ui.M5Label("Bright: 100%", x=1050, y=565,
        text_c=0x8B949E, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_16, parent=page0)

    # Brightness - button (bottom)
    btn_brightness_down = m5ui.M5Button(text="-", x=1050, y=600,
        w=210, h=40, bg_c=0xF85149, text_c=0xFFFFFF,
        font=lv.font_montserrat_20, parent=page0)
    btn_brightness_down.add_event_cb(btn_brightness_down_cb, lv.EVENT.ALL, None)

    # Ctrl+L button (anchor at bottom)
    btn_clear = m5ui.M5Button(text="Ctrl+L", x=1050, y=650,
        w=210, h=52, bg_c=0x6E7681, text_c=0xFFFFFF,
        font=lv.font_montserrat_24, parent=page0)
    btn_clear.add_event_cb(btn_clear_cb, lv.EVENT.ALL, None)

    # ── Confirmation page ─────────────────────────────────────────────────────
    page_confirm = m5ui.M5Page(bg_c=0x000000)

    m5ui.M5Label("⚠  Clear all log data?", x=320, y=220,
        text_c=0xF85149, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_24, parent=page_confirm)

    m5ui.M5Label("This cannot be undone.", x=390, y=270,
        text_c=0x8B949E, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_16, parent=page_confirm)

    m5ui.M5Label("Make sure you retrieved the log via USB first!",
        x=220, y=300,
        text_c=0xD29922, bg_c=0x000000, bg_opa=0,
        font=lv.font_montserrat_16, parent=page_confirm)

    btn_yes = m5ui.M5Button(text="YES, CLEAR", x=200, y=400,
        w=280, h=80, bg_c=0xDA3633, text_c=0xFFFFFF,
        font=lv.font_montserrat_24, parent=page_confirm)
    btn_yes.add_event_cb(btn_yes_cb, lv.EVENT.ALL, None)

    btn_no = m5ui.M5Button(text="NO, CANCEL", x=780, y=400,
        w=280, h=80, bg_c=0x238636, text_c=0xFFFFFF,
        font=lv.font_montserrat_24, parent=page_confirm)
    btn_no.add_event_cb(btn_no_cb, lv.EVENT.ALL, None)

    page0.screen_load()

# ─── WiFi scanning ────────────────────────────────────────────────────────────

def add_device(d):
    global write_index
    devices[write_index] = d
    write_index = (write_index + 1) % MAX_DEVICES

def do_wifi_scan():
    global wifi_count
    if system_state != STATE_SCANNING:
        return
    try:
        sta = network.WLAN(network.STA_IF)
        if not sta.active():
            sta.active(True)
            utime.sleep_ms(200)
        results = sta.scan()
        for r in results:
            try:
                ssid = safe_ssid(r[0])
                mac  = fmt_mac(r[1])
                chan = r[2]
                rssi = r[3]
                enc  = enc_str(r[4])
                if mac in seen_macs:
                    continue
                seen_macs.add(mac)
                wifi_count += 1
                d = (ssid, mac, rssi, chan, enc)
                add_device(d)
                log_line(d)
                if log_full:
                    break
            except Exception as e:
                print("AP parse error:", e)
        refresh_rows()
        gc.collect()
    except Exception as e:
        print("WiFi scan error:", e)
        gc.collect()

# ─── Main ─────────────────────────────────────────────────────────────────────

def show_bootscreen():
    try:
        M5.Lcd.drawJpg("/flash/bootscreen.jpg", 0, 0)
        utime.sleep_ms(3000)
    except Exception as e:
        print("Bootscreen error:", e)

def setup():
    M5.begin()
    Widgets.setRotation(1)
    show_bootscreen()
    build_ui()
    init_gps()
    load_brightness()
    update_header()
    update_gps_label()
    refresh_rows()
    update_size_label()
    size = get_log_size()
    if size > 0:
        set_status("Existing log: {}. Press START to continue.".format(
            fmt_size(size)), 0x58A6FF)
    gc.collect()

def loop():
    global last_scan, last_header, last_gps, confirm_mode, confirm_timeout
    M5.update()
    now = utime.ticks_ms()

    # Confirmation timeout — revert if no second tap within 2 seconds
    if confirm_mode and utime.ticks_diff(now, confirm_timeout) >= 2000:
        confirm_mode = False
        btn_scan.set_btn_text("STOP")
        btn_scan.set_style_bg_color(
            lv.color_hex(0xDA3633), lv.PART.MAIN | lv.STATE.DEFAULT)
        set_status("Confirmation cancelled.", 0x8B949E)

    # Update header every second
    if utime.ticks_diff(now, last_header) >= HEADER_INTERVAL_MS:
        last_header = now
        update_header()
        update_gps_label()

    # Read GPS every 500ms
    if utime.ticks_diff(now, last_gps) >= GPS_INTERVAL_MS:
        last_gps = now
        read_gps()

    # WiFi scan every 15 seconds
    if scanning and utime.ticks_diff(now, last_scan) >= SCAN_INTERVAL_MS:
        last_scan = now
        do_wifi_scan()

if __name__ == "__main__":
    try:
        setup()
        while True:
            loop()
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg
            print_error_msg(e)
        except Exception:
            print("Fatal:", e)

# A fresh shirt a day is always a good practice!