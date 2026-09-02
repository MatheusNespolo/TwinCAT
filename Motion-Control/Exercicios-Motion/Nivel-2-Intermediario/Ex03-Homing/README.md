# Exercício 03 — Referenciamento (Homing) e Interlock de Ciclo

**Nível:** 2 — Intermediário

## Cenário

Um eixo linear (fuso) só tem sua posição absoluta conhecida depois de ser referenciado
(homing). O sensor de home está fisicamente na posição "0" do eixo. **Nenhum comando de
movimento automático deve ser aceito antes da referência ser concluída.**

Este exercício isola exatamente o item 2 e 3 da prova prática de certificação: configurar a
referência de um motor e impedir que o ciclo comece sem que a referência tenha sido feita.

## O que fazer

Usando `GVL_Axes.Axis1` (eixo linear, escala 10 mm/volta):

1. Configure a escala do `Axis1` em *NC → Axes → Axis 1 → Enc → Parameter → Scaling Factor Numerator*
   para refletir 10 mm por volta do motor.
2. Declare uma entrada digital `xSensorHome : BOOL` simulando o sensor de home físico na posição 0.
3. Declare um botão `xBotaoReferencia : BOOL`.
4. Instancie `MC_Home` com:
   - `Execute := xBotaoReferencia` (só deve poder ser acionado com o eixo habilitado)
   - `Position := 0.0` (a posição que o eixo assume ao encontrar o home)
   - Sinal do sensor de home (`bCalibrationCam` ou equivalente na sua versão da lib) ligado a
     `xSensorHome` quando a lib exigir (em algumas versões o sensor é lido via hardware/NC,
     não como parâmetro do bloco — deixe isso comentado explicando a diferença).
5. Crie uma saída `xEixoReferenciado : BOOL` que fica `TRUE` após `MC_Home.Done = TRUE` e só volta
   a `FALSE` se o eixo for desabilitado (perda de referência ao desligar).
6. Crie um interlock: `xPermiteIniciarCiclo := xEixoHabilitado AND xEixoReferenciado`.

## Elementos da biblioteca Motion exigidos

- `MC_Home` (executa a rotina de busca de referência)
- `Axis.Status.HomingDone` / bit próprio de referência mantido pela sua lógica
- Interlock lógico (`AND`) combinando habilitação + referência

## Critérios de aceite

- Sem `xBotaoReferencia`, o eixo nunca fica com `xEixoReferenciado = TRUE`.
- Enquanto `MC_Home.Busy = TRUE`, nenhum outro comando de movimento pode ser aceito
  (adicione essa trava mesmo que o exercício não peça outro movimento aqui — é um hábito
  que a prova cobra).
- Ao desabilitar o eixo (`MC_Power.Enable = FALSE`), `xEixoReferenciado` deve voltar a `FALSE`
  (na prova real, o eixo linear perde a referência ao desligar; já o eixo rotativo, não —
  isso é tratado no Exercício 04).

## Dica

Pense em `xEixoReferenciado` como um **flip-flop (SET/RESET)**: SET quando `MC_Home.Done`,
RESET quando o eixo é desabilitado ou reporta erro.
