# 2026-09-19 — CX9240 + HiveMQ Cloud + sistema real: notas de integração

> Resumo da sessão de hoje, para consumo por outro agente que continuará a
> documentação no repositório `DataFlowInventory`. Contexto prévio relevante:
> `docs/2026-09-08-cx9240-mqtt-historian-design.md`,
> `docs/2026-09-08-cx9240-mqtt-historian-plan.md`,
> `docs/comissionamento-rt-linux.md`, e o PR #6
> (`fix/mqtt-message-queue-wiring`, já mergeado em `main`) que corrigiu o bug
> real de fiação da fila MQTT (`ipMessageQueue`) validado com o simulador.

## Objetivo de hoje

Testar o CX9240 — já com o pipeline MQTT→SQLite corrigido (PR #6) — contra o
**sistema real** (Arduino/ESP32 + servidor Node + dashboard), não mais o
simulador isolado, e com o broker MQTT migrado de Mosquitto local para
**HiveMQ Cloud** (remoto, TLS).

## Análise de impacto — broker remoto (antes do teste)

Antes de testar, revisamos o que muda ao trocar Mosquitto local por HiveMQ
Cloud:

- **Fiação de TLS no `FB_DfiMqttSubscriber` conferida contra a doc oficial do
  TF6701** (`ST_IotMqttTLS`): não existe um flag "habilitar TLS" separado —
  preencher `stTLS.sCA` já ativa o modo TLS. O código já fazia isso
  corretamente (`ApplyBrokerParams`, `IF stConfig.bUseTls THEN
  fbMqtt.stTLS.sCA := stConfig.sCaCertPath`). **Nenhum bug de código aqui.**
- Credenciais reais (`mqtt_user`/`mqtt_pass`) só existem no
  `/etc/dfi/historian.conf` do CX9240, nunca no git (mesma regra de sempre —
  ver [[wifi-credentials-leaked-history]] como lembrete do porquê).
- Bundle de CA (`/etc/ssl/certs/ca-certificates.crt`) confirmado presente no
  CX apesar do reflash anterior ter derrubado outras coisas.
- Egress de rede muda de natureza: antes só LAN, agora precisa de saída
  outbound real (DNS + TCP 8883) — foi exatamente aqui que apareceram os
  problemas (ver abaixo).
- Relógio do CX precisa estar correto para validação de certificado TLS (não
  só para os timestamps como antes).

## Problemas encontrados, em cadeia, e causa raiz de cada um

Depois de preencher o `historian.conf` com os dados do HiveMQ e ativar a
configuração, `bMqttConnected` ficou `FALSE` (e `bDbConnected` junto, como
efeito colateral esperado — sem MQTT o buffer não enche e o writer nunca sai
de `IDLE`). Diagnóstico em 3 camadas:

**1. `mqtt_host` com esquema de URI incluído.** O console do HiveMQ Cloud
mostra a "Cluster URL" completa (`mqtts://<cluster>.s1.eu.hivemq.cloud`), mas
`FB_IotMqttClient.sHostName` espera só o hostname puro. Corrigido removendo o
prefixo `mqtts://` do valor em `historian.conf`. Não resolveu sozinho — havia
um segundo problema por trás.

**2. Diagnóstico mais fundo via campos do `FB_IotMqttClient` nunca antes
usados no projeto:** `bError`, `hrErrorCode`, `eConnectionState` (achados na
doc oficial do TF6701 — não estavam fiados nos outputs do
`FB_DfiMqttSubscriber`, mas dá pra observar direto via watch em
`GVL_Dfi.fbSub.fbMqtt.*`). Resultado: `eConnectionState =
MQTT_ERR_NOT_FOUND`.

**3. Rastreado até a causa raiz real, fora do TwinCAT inteiramente:**
- `getent hosts <cluster>` não resolvia nada.
- `resolvectl status` mostrava as duas interfaces de rede do CX
  (`end0`/`end1`) sem `Default Route`.
- `ping 8.8.8.8` → `Network is unreachable`.
- `ip addr show` revelou que `end0` estava com IP **link-local
  autoatribuído** (`169.254.x.x`) — ou seja, **nenhum servidor DHCP
  respondeu**. Causa física: hoje o CX9240 estava ligado **ponto-a-ponto no
  Ethernet do PC de engenharia**, não na rede do SENAI como nas sessões
  anteriores — sem gateway, sem DNS, sem internet.

## Correção aplicada

**Internet Connection Sharing (ICS) do Windows**, no PC de engenharia:
adaptador com internet (Wi-Fi) compartilhado através do adaptador Ethernet
ligado ao CX9240. Isso fixa o Ethernet do PC em `192.168.137.1/24` e liga
DHCP+NAT+DNS relay nele automaticamente. Depois de `sudo networkctl
reconfigure end0` no CX, ele recebeu lease real (`192.168.137.x`), DNS passou
a resolver, e a conexão TLS com o HiveMQ Cloud foi estabelecida.

**Nenhuma mudança de código PLC foi necessária hoje** — foi inteiramente
diagnóstico de rede/config (o valor de `mqtt_host`, e a rota de rede do
CX9240 em si).

## Efeito colateral observado — necessidade a registrar

Ativar o ICS no PC **causou conflito de rede que exigiu trocar o Wi-Fi ao qual
o ESP32 se conecta**. Não investigado a fundo hoje, mas é uma necessidade de
integração real a documentar: quando o PC de engenharia passa a rotear/NATear
a rede do CX9240 via ICS, isso pode colidir com a topologia de rede que o
resto do sistema (ESP32) já está usando. Para produção, isso reforça que o
CX9240 precisa de uma saída de rede própria e estável (não dependente do PC
de engenharia estar ligado e compartilhando), especialmente se o broker
continuar sendo remoto (HiveMQ Cloud) em vez de local.

## Resultado — validação end-to-end (primeira vez com o sistema real)

Após a correção, pedido de peça real via o sistema completo (Arduino/ESP32 →
servidor Node → dashboard) gerou gravação correta em **ambas** as tabelas
pela primeira vez:

- `estoque_hist`: linhas `origem='mudanca'` e `origem='periodico'`, valores e
  timestamps locais corretos.
- `eventos_hist`: linhas reais de `evento='pedido'`, `'entrega'`, e até
  `'inicio'` (evento de boot do firmware, com `payload_raw` JSON completo) —
  **esse caminho nunca tinha sido exercitado antes** (o simulador Node só
  publicava `dataflow/estoque`, nunca `dataflow/eventos`). Fecha o último gap
  de cobertura que ficou pendente da sessão de 16/09.

## Estado do repositório

- PR #6 (`fix/mqtt-message-queue-wiring`) confirmado **mergeado em `main`**
  (commit `89b39af`).
- Nenhum commit novo necessário por causa do teste de hoje — só este arquivo
  de notas.
- `test/win11-usermode-runtime` (17/09) continua parado/não mergeado: o
  TwinCAT Usermode Runtime (XarMode) local aparentou problema de
  licenciamento com a TF6420, não investigado a fundo; branch mantido só
  como referência caso decidam retomar essa topologia depois (talvez com um
  projeto do zero, conforme discutido).

## Itens em aberto

- TcUnit suites — ainda não reportadas como executadas/verdes nesta sessão.
- Os 8 cenários de bancada em `roteiro-testes-bancada.md` — ainda não
  rodados formalmente.
- Investigar por que o ICS causou o conflito que forçou trocar o Wi-Fi do
  ESP32 (item novo, acima).
- Decidir a solução de rede definitiva do CX9240 para produção (rede própria
  vs. depender do PC de engenharia via ICS).
- Provedor de banco em ambientes Windows (Usermode Runtime) — discussão
  adiada desde 16/09, ainda não retomada.
