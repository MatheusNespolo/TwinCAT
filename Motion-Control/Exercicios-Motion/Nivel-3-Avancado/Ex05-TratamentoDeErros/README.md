# Exercício 05 — Tratamento de Erros e Reset Global

**Nível:** 3 — Avançado

## Cenário

Em uma máquina automática, qualquer erro de eixo deve parar toda a operação com segurança:
desligar o ciclo automático, desabilitar os eixos e sinalizar a falha. Só depois de um comando de
**Reset** explícito (e com a causa do erro sanada) a máquina pode voltar a funcionar. Além disso,
o botão de reset **não pode interferir** caso seja pressionado durante o ciclo automático normal
(sem erro).

## O que fazer

Usando `GVL_Axes.Axis1` e `GVL_Axes.Axis2`:

1. Declare `xCicloAutomatico : BOOL` representando se a máquina está em ciclo automático
   (pode ser um bit forçado manualmente neste exercício, sem máquina de estados ainda —
   isso vem no Exercício 06).
2. Declare `xBotaoReset : BOOL`.
3. Crie uma lógica de falha global `xFalhaEixos : BOOL` que fica `TRUE` se **qualquer** dos dois
   eixos reportar `Status.Error = TRUE`.
4. Ao detectar `xFalhaEixos`, force `xCicloAutomatico := FALSE` (desliga o ciclo automaticamente)
   e desabilite os dois eixos (via `MC_Power.Enable := FALSE`).
5. Instancie `MC_Reset` para cada eixo, disparado por `xBotaoReset AND xFalhaEixos`
   (ou seja: **só reseta se realmente houver falha** — isso implementa "o botão de reset não deve
   interferir na máquina durante o ciclo automático" quando não há erro).
6. Só permita reabilitar os eixos depois que ambos os `MC_Reset.Done = TRUE`.
7. Exponha `xSinalizaFalha : BOOL` (para uma eventual lâmpada/sinaleiro) que só desliga depois do
   reset bem-sucedido.

## Elementos da biblioteca Motion exigidos

- `Axis.Status.Error` (bit de erro do eixo)
- `MC_Reset` (limpa o erro do eixo, permitindo reabilitação)
- `MC_Power.Enable` (para forçar desabilitação em caso de falha)

## Critérios de aceite

- Um erro em **qualquer** eixo deve derrubar o ciclo automático e desabilitar **ambos** os eixos
  (falha de um afeta a máquina inteira, já que os movimentos são coordenados).
- Pressionar `xBotaoReset` sem haver falha não deve ter nenhum efeito perceptível na máquina.
- Depois do reset, a máquina deve poder ser reabilitada e um **novo ciclo automático** deve poder
  ser iniciado normalmente (não pode "travar" definitivamente após um erro).
- `xSinalizaFalha` deve continuar `TRUE` durante todo o tempo em que o erro não foi resetado, mesmo
  que a causa física do erro já tenha sumido.

## Dica

Este exercício implementa diretamente os itens 6 e 7 e 9 da prova prática:
*"Se ocorrer qualquer erro o sistema todo para... o sistema é normalizado com o botão de reset"*,
*"deve ser possível iniciar um novo ciclo automático"* e *"Botão de Reset não deve interferir na
máquina durante o ciclo automático"*.
