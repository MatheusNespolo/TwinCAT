# Comunicacao-Rede

Comunicação entre runtimes/dispositivos: ADS e Modbus TCP.

## Projetos

- **[Modbus TCP - Client](Modbus%20TCP%20-%20Client/)** — máquina de estados com `FB_MBReadRegs`/`FB_MBWriteRegs` e tratamento de erro.
- **[Modbus TCP - Server](Modbus%20TCP%20-%20Server/)** — mapeamento de coils/registros (`GVL`) ligado a um device de I/O; servidor configurado por hardware, não por código.
- **[Demokit_Side](Demokit_Side/)** — lado servidor de um par de comunicação ADS: expõe `iVar`/`bVar` via `%M*`.
- **[LocalPC_Side](LocalPC_Side/)** — lado cliente do mesmo par: lê as variáveis remotas via `ADSREAD` (NetID/porta/offset).

## Possíveis assuntos futuros

- MQTT / OPC UA (o projeto `OPC_Conectivity_Test` em Inacabados está vazio — seria um bom candidato a completar)
- Diagnóstico de rede EtherCAT
- TF6000 (TCP/IP) genérico

> Os projetos [`OPC_Conectivity_Test`](../Inacabados/Comunicacao-Rede/OPC_Conectivity_Test/) e [`FTP-CE`](../Inacabados/Comunicacao-Rede/FTP-CE/) também são desse assunto, mas estão em [`Inacabados/`](../Inacabados/) por não terem lógica implementada.
