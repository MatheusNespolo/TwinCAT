# TwinCAT

Repositório de estudo e portfólio com projetos TwinCAT3 (Beckhoff): PLC estruturado, motion control, comunicação industrial, banco de dados, HMI e safety (TwinSAFE).

## Estrutura

Os projetos ficam organizados por assunto/subtema. Cada pasta de categoria tem seu próprio `README.md` com a lista de projetos e sugestões do que ainda pode ser explorado naquele tema.

| Pasta | Assunto |
|---|---|
| [`PLC-Fundamentos/`](PLC-Fundamentos/) | Programação estruturada básica de PLC |
| [`OOP/`](OOP/) | Orientação a objetos aplicada a PLC (interfaces, herança, FBs) |
| [`Motion-Control/`](Motion-Control/) | Controle de movimento (NC / blocos `MC_*`) |
| [`Comunicacao-Rede/`](Comunicacao-Rede/) | ADS e Modbus TCP |
| [`Banco-de-Dados/`](Banco-de-Dados/) | TF6420 Database Server |
| [`HMI-Supervisorio/`](HMI-Supervisorio/) | TwinCAT HMI / supervisório |
| [`Safety/`](Safety/) | TwinSAFE |
| [`Inacabados/`](Inacabados/) | Projetos sem lógica implementada — ver critério abaixo |

## Projetos inacabados

Todo projeto que é só um esqueleto de template (sem lógica de PLC implementada) ou uma solução sem nenhum sub-projeto anexado fica isolado em [`Inacabados/`](Inacabados/), subdividido pelas mesmas categorias acima. Isso evita confundir um exemplo funcional com um estudo em andamento. Cada item lá é candidato a virar um exemplo completo — veja o README de cada categoria para sugestões.

## Como abrir um projeto

1. Requer **TwinCAT XAE Shell** ou **Visual Studio com TwinCAT3** instalado, e a versão de runtime TwinCAT3 correspondente para rodar/simular.
2. Abra o arquivo `.sln` dentro da pasta do projeto desejado.
3. Projetos de **TwinCAT HMI** restauram os pacotes NuGet (`Packages/`) automaticamente na primeira compilação/publicação — essa pasta não é versionada (ver `.gitignore` abaixo), então é normal ela não existir logo após o clone.
4. Pastas como `bin/`, `obj/`, `.vs/` e `_Boot/` também são geradas automaticamente pela IDE/build e não fazem parte do conteúdo do projeto.

## Sobre o `.gitignore`

O `.gitignore` da raiz cobre arquivos específicos de PLC/TwinCAT (`.tpy`, `.compiled-library`, `_Boot/`, etc.), o template padrão de Visual Studio (`.vs/`, `bin/`, `obj/`, `*.suo`, `*.user`) e o cache/pacotes do TwinCAT HMI (`.engineering_servers/`, `Packages/`, `node_modules/`). Antes de dar `git add`, vale rodar `git status` e conferir se algum desses padrões não escapou — build artifacts não devem ser commitados.

## Próximos assuntos

Ideias para expandir o repositório, por categoria:

- **PLC-Fundamentos**: máquinas de estado genéricas, testes unitários com TcUnit
- **OOP**: padrões de projeto (Strategy, Observer) aplicados a PLC, biblioteca de FBs reutilizáveis
- **Motion-Control**: multi-eixo/interpolação, cames eletrônicos, CNC simples
- **Comunicacao-Rede**: MQTT, OPC UA, diagnóstico EtherCAT
- **Banco-de-Dados**: logging histórico com Grafana/InfluxDB via TF6420
- **HMI-Supervisorio**: dashboard de produção, HMI responsivo, autenticação de usuários
- **Safety**: mais dispositivos FSOES, SafeMotion
- **Inacabados**: completar qualquer um dos esqueletos listados lá
