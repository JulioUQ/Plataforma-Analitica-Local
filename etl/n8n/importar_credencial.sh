#!/bin/sh
# Se ejecuta dentro del contenedor n8n. Lee el JSON de la credencial por stdin,
# quita un BOM UTF-8 inicial si lo hay, lo importa y borra los temporales.
umask 077
cat > /tmp/cred.raw
if [ "$(head -c 3 /tmp/cred.raw | od -An -tx1 | tr -d ' \n')" = "efbbbf" ]; then
  tail -c +4 /tmp/cred.raw > /tmp/cred.json
else
  cp /tmp/cred.raw /tmp/cred.json
fi
rm -f /tmp/cred.raw
n8n import:credentials --input=/tmp/cred.json
rc=$?
rm -f /tmp/cred.json
exit $rc
