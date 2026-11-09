# Comunicacao-Rede

Comunicação entre runtimes/dispositivos: ADS e Modbus TCP.

## Projetos

- **[Modbus TCP - Client](Modbus%20TCP%20-%20Client/)** — máquina de estados com `FB_MBReadRegs`/`FB_MBWriteRegs` e tratamento de erro.
- **[Modbus TCP - Server](Modbus%20TCP%20-%20Server/)** — mapeamento de coils/registros (`GVL`) ligado a um device de I/O; servidor configurado por hardware, não por código.
- **[Demokit_Side](Demokit_Side/)** — lado servidor de um par de comunicação ADS: expõe `iVar`/`bVar` via `%M*`.
- **[LocalPC_Side](LocalPC_Side/)** — lado cliente do mesmo par: lê as variáveis remotas via `ADSREAD` (NetID/porta/offset).
- **[EtherNet-IP Adapter](EtherNet-IP%20Adapter/)** e **[EtherNet-IP Scanner](EtherNet-IP%20Scanner/)** — par adapter/scanner (TF6280/TF6281); o Scanner inclui o arquivo `.eds`.
- **[Profinet Device](Profinet%20Device/)** e **[Profinet Controller](Profinet%20Controller/)** — par device/controller (TF6270/TF6271).
- **[Benchmark-Protocolos](Benchmark-Protocolos/)** — mede o custo de ADS, OPC UA e Modbus TCP para o mesmo dado (tempo de eco e de leitura, p50/p95/p99) com um cliente Python; inclui o eco em ST e um simulador para dry-run. Medições em hardware real ainda pendentes.

## Possíveis assuntos futuros

- MQTT / OPC UA (o projeto `OPC_Conectivity_Test` em Inacabados está vazio — seria um bom candidato a completar)
- Diagnóstico de rede EtherCAT
- TF6000 (TCP/IP) genérico

> Os projetos [`OPC_Conectivity_Test`](../Inacabados/Comunicacao-Rede/OPC_Conectivity_Test/) e [`FTP-CE`](../Inacabados/Comunicacao-Rede/FTP-CE/) também são desse assunto, mas estão em [`Inacabados/`](../Inacabados/) por não terem lógica implementada.
