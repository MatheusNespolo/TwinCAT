# Introdução
Diferente das notas de Conectividade que envolvem um TF (funcionalidade licenciada, como [[TF6100 - OPC UA]] ou [[TF6420 - Database Server]]), a comunicação de um script Python com o TwinCAT não exige nenhuma licença adicional: ela usa o **ADS**, o protocolo nativo de comunicação do TwinCAT, que já vem incluso em qualquer instalação. Essa nota documenta como acessar variáveis de um projeto PLC a partir de um script Python usando a biblioteca open-source `pyads`.

# O que é o ADS
ADS (Automation Device Specification) é o protocolo interno usado pelo TwinCAT para trocar dados entre seus próprios módulos (PLC, NC, I/O) e também com aplicações externas. Cada módulo do TwinCAT (e cada aplicação cliente) é tratado como um "dispositivo ADS" endereçável.
- **AmsNetId**: identifica um roteador de mensagens (PC ou controlador) na rede. É uma extensão do endereço IP, por exemplo `192.168.1.11.1.1` para o IP `192.168.1.11`;
- **ADS-Port**: identifica, dentro de um dispositivo, qual módulo deve receber a mensagem (por exemplo, a porta 851 é o primeiro Runtime de PLC).
Esse é o mesmo conceito de rota ADS já mencionado em [[TwinCAT-Linux Introduction]] (ao final da configuração da interface EtherCAT) e em [[Publisher-Subscriber (Beckhoff RT Linux - CX8290)]] (comando `adstool addroute`) — a diferença é que, em vez de rotear dados entre dois controladores TwinCAT, aqui é uma aplicação Python externa que se conecta como cliente ADS.

## AMS NetId
Os dispositivos do TwinCAT são identificados pelo AMS NetId. Esse ID é configurado por um conjunto de 8 bytes.
Os 4 primeiros são livre para configuração e os 2 últimos são a máscara de sub-rede (.1.1)
Cuidado ao alterar o AMS NetId de um determinado dispositivos, esses endereços não podem estar duplicados na rede.

### Conferindo AMS NetId
1. Método 1: Com um projeto do TwinCAT aberto e a conexão da rota ADS estabelecida com o Target, expanda a seção SYSTEM e clique duas vezes em "Routes" e depois navegue até a aba "NetID Management".
![[Routes.png]]
![[NetId Management.png]]
Obs.: Nessa aba podemos ver tanto o AMS NetId do PC de engenharia que está rodando o XAE (Local) como também o endereço do PC industrial conectado como Target da solução, rodando o XAR.
2. Método 2: Na barra de ferramentas do Windows clique com o botão direito no símbolo do TwinCAT, vá na opção "Router" e depois clique em "Change AMS NetId".
![[Router.png]]
![[Change AMS NetId.png]]
Obs.: Essa janela mostra apenas o AMS NetId local.

# pyads — o cliente Python para TwinCAT ADS
[pyads](https://github.com/stlehmann/pyads) é uma biblioteca Python open-source (não é um produto Beckhoff) que "embrulha" a API C do ADS (`TcAdsDll.dll` no Windows, `adslib.so` no Linux), permitindo ler e escrever variáveis do PLC diretamente em Python. Suporta tanto TwinCAT 2 quanto TwinCAT 3.
Instalação:
```bash
pip install pyads
```

## Exemplo prático — lendo e escrevendo uma variável
Primeiro, numa solução do TwinCAT XAE, adicione um programa de PLC.
![[Add New Item... TwinCAT PLC Project.png]]
Nesse programa vamos adicionar uma GVL, nomea-la apenas como GVL, e criar duas variáveis inteiras que faremos a manipulação a fim de exemplificar esse tipo de comunicação.
![[Variáveis na GVL.png]]
Feito isso, podemos interagir com a solução do TwinCAT criada através do programa em Python abaixo:
```python
import pyads

# Conexão com o PLC (porta 851 = primeiro Runtime de PLC)
plc = pyads.Connection("5.162.186.144.1.1", pyads.PORT_TC3PLC1)

#AMS NetId do controlador TwinCAT, porta 851
plc.open()

# Leitura de uma variável declarada em uma GVL
valor = plc.read_by_name("GVL.Contador")
print(f"Valor atual: {valor}")

# Escrita de uma variável
plc.write_by_name("GVL.SetpointVelocidade", 42.0)

plc.close()
```
Esse programa executa 3 comandos básicos:
1. Estabelece uma conexão com o target através do AMS NetId informado na função "Connection" do pyads;
2. Lê o valor da variável "Contador" a partir do nome declarado no programa de PLC, atribuindo e mostrando o valor com a variável "valor" do Python;
3. Escreve o valor 42.0 na variável "SetpointVelocidade".
Depois de executar esse programa no terminal, a saída deve mostrar:
- "Valor atual: 50" (valor de inicialização configurado na declaração)
E na GVL dentro do TwinCAT podemos ver a alteração da variável que foi escrita:
![[SetpointVelocidade Alterado.png]]
Obs.: O foco desse documento não é instruir na instalação do Python em si, não há indicação de uma IDE ou ambiente de desenvolvimento que deva ser usado. Para criação desse material foi utilizado o Visual Studio Code, mas você pode repetir o processo em qualquer outra IDE que permita criar um arquivo em .py e executa-lo em um terminal.
Assim como em [[Javascript]] (`document.querySelector`) e no [[TwinCAT HMI Creator]] (`TcHmi.EventProvider.register`), o pyads segue o mesmo espírito de "referenciar algo pelo nome e reagir/alterar seu valor" — aqui aplicado a variáveis do PLC em vez de elementos de uma página.

# Casos de uso práticos
- **Logging externo em banco de dados**: usar `pyads` para ler variáveis do PLC periodicamente e gravá-las em um banco com uma biblioteca Python de banco de dados (por exemplo `mysql-connector-python` ou `psycopg2`, aplicando o que já foi praticado em [[MySQL]] e [[Postgre]]). É o caminho inverso da [[TF6420 - Database Server]]: em vez do TwinCAT escrever no banco a partir de dentro do projeto PLC, é um script Python externo que lê o PLC e escreve no banco;
- **Scripts de teste e automação de comissionamento**: escrever pequenos scripts Python que forçam valores de teste em variáveis do PLC e validam o resultado, um equivalente simplificado (e fora do ambiente TwinCAT) do que o [[PLC OOP Basics|TcUnit]] faz dentro do próprio PLC;
- **Análise de dados**: como já visto em [[Entendendo algoritmos]] (que referencia um [repositório Python próprio](https://github.com/MatheusNespolo/Python/tree/main/Algoritmos)), dados lidos via `pyads` podem alimentar diretamente scripts de análise ou estruturas de dados em Python (arrays, tabelas hash) para processamento fora do ciclo de tempo real do PLC.

# Automation Interface — outra forma de "scriptar" o TwinCAT
Vale diferenciar o pyads (que fala com o **Runtime** do PLC já em execução, via ADS) da **TwinCAT Automation Interface**, um recurso oficial da Beckhoff que permite automatizar o **ambiente de engenharia** (criar/configurar projetos, adicionar dispositivos, compilar) através de linguagens compatíveis com COM, como PowerShell ou IronPython — não o Python padrão (CPython). Ou seja, são dois "scripts" com propósitos diferentes: Automation Interface configura o projeto antes do deploy; pyads troca dados com o projeto depois que ele já está rodando.

# Referências
### Oficiais (Beckhoff Infosys)
- [Infosys - ADS](https://infosys.beckhoff.com/content/1033/tcinfosys3/11291871243.html)
- [Infosys - ADS device identification](https://infosys.beckhoff.com/content/1033/tcadscommon/12439473419.html)
- [Infosys - Using the Automation Interface within scripting languages](https://infosys.beckhoff.com/content/1033/tc3_automationinterface/242715915.html)
### Independentes (comunidade)
- [GitHub - stlehmann/pyads](https://github.com/stlehmann/pyads)
- [Documentação pyads (Read the Docs)](https://pyads.readthedocs.io/)
- [soup01.com - Using Python to Communicate with TwinCAT by ADS](http://soup01.com/en/2022/06/02/beckhoffusing-python-to-communicate-with-twincat-by-ads/)
