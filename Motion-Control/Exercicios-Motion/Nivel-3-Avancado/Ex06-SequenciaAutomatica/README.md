# Exercício 06 — Máquina de Estados para Ciclo Automático Contínuo

**Nível:** 3 — Avançado

## Cenário

Uma ferramenta linear (fuso) precisa avançar até uma posição de trabalho, aguardar um tempo
(simulando uma operação), recuar, e repetir esse ciclo continuamente até receber um comando de
parada — que só deve efetivar a parada **ao final do ciclo em andamento** (não interrompe no meio
de um avanço).

Este exercício treina a estrutura de **máquina de estados (`CASE`)** que será a espinha dorsal do
simulado de certificação no Nível 4.

## O que fazer

Usando `GVL_Axes.Axis1` (eixo linear, já habilitado e referenciado — assuma isso como dado):

1. Crie um DUT (Data Unit Type) `E_EstadoCiclo` (enum) com estados: `PARADO`, `AVANCA`, `AGUARDA`,
   `RECUA` (no TwinCAT, `TYPE...END_TYPE` de um enum precisa ser um objeto `DUT` separado do POU —
   veja o gabarito `E_EstadoCiclo.TcDUT` desta pasta).
2. Declare `xLigarCiclo : BOOL` e `xDesligarCiclo : BOOL`.
3. Implemente a máquina de estados via `CASE eEstado OF`:
   - `PARADO`: se `xLigarCiclo`, vai para `AVANCA`.
   - `AVANCA`: comanda `MC_MoveAbsolute` até `100.0` mm; quando `Done`, vai para `AGUARDA`.
   - `AGUARDA`: usa um `TON` de 1 segundo; ao expirar, vai para `RECUA`.
   - `RECUA`: comanda `MC_MoveAbsolute` até `10.0` mm; quando `Done`:
     - se `xDesligarCiclo` foi acionado durante o ciclo, vai para `PARADO`;
     - senão, volta para `AVANCA` (ciclo contínuo).
4. Exponha `xCicloLigado : BOOL` (verdadeiro em qualquer estado diferente de `PARADO`).

## Elementos da biblioteca Motion exigidos

- `MC_MoveAbsolute` (usado duas vezes: avanço e recuo)
- Estrutura `CASE` como máquina de estados (não é bloco de Motion, mas é o padrão exigido pela
  prova para orquestrar múltiplos movimentos em sequência)
- `TON` (temporizador de espera, `Tc2_Standard`/`Tc2_System`, já usado no restante do repositório)

## Critérios de aceite

- O ciclo deve repetir `AVANCA → AGUARDA → RECUA` continuamente enquanto `xDesligarCiclo` não for
  acionado.
- Acionar `xDesligarCiclo` no meio do avanço **não deve interromper** o movimento atual — a parada
  só ocorre depois que o ciclo completo (avanço + espera + recuo) termina.
- `xCicloLigado` deve refletir corretamente se a máquina está ou não em operação.
- Nenhum novo `MC_MoveAbsolute` deve ser disparado enquanto o anterior ainda está `Busy`.

## Dica

Guarde o comando de desligar em uma variável auxiliar (`xPedidoParada`) setada quando
`xDesligarCiclo` for pressionado e só consultada no estado `RECUA` — assim você "lembra" do pedido
mesmo que o botão já tenha sido solto antes do fim do ciclo.
