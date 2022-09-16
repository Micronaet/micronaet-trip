@echo off
echo **********************************************************
echo * PARAMETERS                                             *
echo **********************************************************
set logfile=s:\administrator\comandi\log\edi.log
set messaggio=Spooler EDI
echo %date% %time% Start %messaggio% >> %logfile%

echo Absolute path setup:
set base=S:\script\
set mexal=C:\Passepartout\PassClient\mxdesk1297479000\
set python=C:\Python27\

echo **********************************************************
echo * EDI ORDER OPERATIONS                                   *
echo **********************************************************
s:
cd %base%

echo Import ELI:
"%python%python.exe" prepare_s.py ELI

echo Import BIB:
"%python%python.exe" prepare_s.py BIB

echo Import SAR:
"%python%python.exe" prepare_s.py SAR

echo Import ITC:
"%python%python.exe" prepare_s.py ITC

echo Import SIR:
"%python%python.exe" prepare_s.py SIR

echo Import MSC:
"%python%python.exe" prepare_s.py MSC

echo Import FAB:
"%python%python.exe" prepare_s.py FAB

echo Import HOS:
"%python%python.exe" prepare_s.py HOS

echo Import MRK:
"%python%python.exe" prepare_s.py MRK

echo **********************************************************
echo * OPERAZIONI CELLA                                       *
echo **********************************************************
echo Cella esportazione odini:
%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479TABLET@sprix4 -kedi:edi

echo Cella esportazione lotti e prodotti:
%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479TABLET@sprix9 -kedi:edi

echo **********************************************************
echo * PIATTAFORMA:                                           *
echo **********************************************************
echo Piattaforma: OF scaricati e salvati su file, prelevati BF da file a ODOO
cd %base%elior\platform\script
call preleva_of_manda_bf.bat

echo Piattaforma: carica OF in Mexal
%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479ELI001@sprix8 -kedi:edi

echo Piattaforma: Stato magazzino giornaliero
%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479ELI001@sprix9 -kedi:edi

echo **********************************************************
echo * SIR                                                    *
echo **********************************************************
echo SIR: Operazioni extra per il portale
cd %base%SIR\stock
call %base%SIR\stock\extract_stock_s.bat
%python%python.exe %base%SIR\stock\portal_sir_s.py

%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479SIR001@sprix4 -kedi:edi

echo **********************************************************
echo * NON ATTIVI QUESTI:                                     *
echo **********************************************************
rem echo Convert and import SAR:
rem "%python%python.exe" csv2txt.py
rem "%python%python.exe" prepare_s.py SAR
rem echo Import SDX:
rem "%python%python.exe" prepare_s.py SDX

echo **********************************************************
echo * STAMPA PROGRESSIVI DI MAGAZZINO:                       *
echo **********************************************************
%echo Export Stampa progressivi di magazzino:
%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479MA001@sprix9 -kedi:edi

echo **********************************************************
echo * MARKAS:                                                *
echo **********************************************************
echo Markas convert attachments
call S:\script\markas\order\script\import.bat

echo **********************************************************
echo * END OPERATIONS:                                        *
echo **********************************************************
echo %date% %time% Stop %messaggio% >> %logfile%
