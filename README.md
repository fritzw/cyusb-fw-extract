# cyusb-fw-extract.py 
Extract firmware from Cypress USB script files 

This program attempts to create fxload-compatible firmware images by
analyzing a supplied Cypress USB script file.  Cypress USB script files
typically have the ".spt" file extension, and are used in devices that
incorporate the Cypress Semiconductor EZ-USB (CY7C68xxx) series
microcontrollers.  These script files are executed on Windows by the Cypress
Generic USB Driver (CyUsb.sys).

## Version History

### Version 0.2 (2025-01-23):
- Ported from Python 2.7 to Python 3

### Version 0.1:
- Original python 2 script by Dwayne C. Litzenberger
- Source: https://ftp.dlitz.net/pub/dlitz/cyusb-fw-extract/0.1/cyusb-fw-extract.py

## Compatibility

This program is known to work for the following firmware(s):
  - ADS Tech Instant Video-To-Go RDX-160 (hardware H.264 encoder)
      + "`vtogold.spt`" on the CD "Instant Video To-Go CD, Ver. 1.2"
  - Lecroy LogicStudio 16 (USB Logic Analyzer)
    (see also: https://sigrok.org/wiki/LeCroy_LogicStudio)
      + "`LogicStudio16Load.spt`" from the `LogicStudio_install_x86.msi`
        inside `logicstudio_32_v1.2.5.0.zip` from the LeCroy Website
        https://www.teledynelecroy.com/support/softwaredownload/logicstudio.aspx
