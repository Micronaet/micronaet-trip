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
echo * GIT UPDATE:                                            *
echo **********************************************************
s:
cd S:\script\git\micronaet-trip
git pull
copy S:\script\git\micronaet-trip\account_trip\spooler\prepare_s.py S:\script\prepare_s.py

echo **********************************************************
echo * PREPROCESS (DOWNLOAD ORDER)                            *
echo **********************************************************
echo * MARKAS:                                                *
echo **********************************************************
echo Update git and convert attachments to order EDI file:
call S:\script\markas\order\script\import.bat

echo **********************************************************
echo * EDI ORDER OPERATIONS                                   *
echo **********************************************************
cd %base%

echo Import DUS:
"%python%python.exe" prepare_s.py DUS

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

echo Import HOS:
"%python%python.exe" prepare_s.py HOS

echo Import FAB:
"%python%python.exe" prepare_s.py FAB

echo Import MRK:
"%python%python.exe" prepare_s.py MRK

echo **********************************************************
echo * OPERAZIONI VIAGGI                                      *
echo **********************************************************
echo Dettaglio documenti per piattaforma (stampa Excel):
%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479A160@sprix3 -kedi:edi


echo **********************************************************
echo * OPERAZIONI CELLA                                       *
echo **********************************************************
rem Cella importa ordini in Mexal (prima di riesportarli)
rem %mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479TABLET@sprix10 -kedi:edi

echo Cella esportazione odini:
%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479TABLET@sprix4 -kedi:edi

echo Cella esportazione lotti e prodotti:
%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479TABLET@sprix9 -kedi:edi

echo Carica tutti i dati nella Cella:
call S:\script\cron\load_freeze\update_freeze_data.cmd
rem call S:\script\cron\load_freeze\update_freeze_product.cmd

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
"%python%python.exe" %base%SIR\stock\portal_sir_s.py

%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479SIR001@sprix4 -kedi:edi

echo **********************************************************
echo * STAMPA PROGRESSIVI DI MAGAZZINO:                       *
echo **********************************************************
%echo Export Stampa progressivi di magazzino:
%mexal%prog\mxdesk.exe -command=mxrs.exe -agfd -t0 -x2 win32g -p297479MA001@sprix9 -kedi:edi

echo **********************************************************
echo * END OPERATIONS:                                        *
echo **********************************************************
echo %date% %time% Stop %messaggio% >> %logfile%
