# CASA — Central de Acompanhamento de Saúde e Ambiente

O **CASA (Central de Acompanhamento de Saúde e Ambiente)** é uma plataforma para aquisição, armazenamento e visualização de dados ambientais coletados por estações baseadas em ESP32.

O sistema foi desenvolvido para permitir a operação de múltiplas estações distribuídas geograficamente, com configuração local por Bluetooth, transmissão dos dados pela internet e armazenamento centralizado para posterior acompanhamento e análise.

O projeto encontra-se atualmente em fase de validação, inicialmente com **6 estações instaladas em diferentes locais**.

---

## Arquitetura

O CASA é composto por quatro partes principais:

* **Firmware das estações:** executado em ESP32 e responsável pela leitura dos sensores e envio das medições;
* **Aplicativo mobile:** utilizado para configurar e cadastrar as estações por Bluetooth;
* **Backend:** API desenvolvida em FastAPI responsável pelo recebimento, autenticação, armazenamento e consulta dos dados;
* **Frontend:** aplicação React para visualização das estações e das medições coletadas.

A infraestrutura do servidor é executada utilizando Docker Compose.

```text
                         ┌──────────────────┐
                         │     Internet     │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │      Caddy       │
                         │ Reverse Proxy    │
                         └───────┬──────────┘
                                 │
                   ┌─────────────┴─────────────┐
                   │                           │
                   ▼                           ▼
          ┌────────────────┐          ┌────────────────┐
          │    Frontend    │          │    Backend     │
          │ React + Nginx  │          │    FastAPI     │
          └────────────────┘          └───────┬────────┘
                                              │
                                              ▼
                                     ┌────────────────┐
                                     │   PostgreSQL   │
                                     └────────────────┘
```

As estações enviam suas medições para a API através do Caddy:

```text
ESP32
  │
  │ HTTP/HTTPS
  ▼
Caddy
  │
  │ /api/measurements
  ▼
FastAPI
  │
  ▼
PostgreSQL
```

---

## Dados coletados

As estações foram projetadas para monitorar diferentes grandezas ambientais.

Atualmente são coletados:

* temperatura;
* umidade relativa;
* pressão atmosférica;
* luminosidade;
* concentração de material particulado PM1.0;
* PM2.5;
* PM4.0;
* PM10;
* concentração numérica de partículas;
* tamanho típico das partículas.

Ainda a utilização de um módulo GPS para atualização periódica da localização das estações.

---

## Estrutura do projeto

A estrutura principal do repositório é:

```text
CASA/
├── backend/
│   ├── alembic/
│   ├── app/
│   ├── Dockerfile
│   ├── alembic.ini
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
│
├── infra/
│   └── Caddyfile
│
├── backups/
│
├── compose.yaml
├── .env
├── .env.example
├── .gitignore
└── README.md
```

O diretório `backups/` é utilizado para backups locais do banco e não deve ser versionado.

---

## Tecnologias utilizadas

### Backend

* Python
* FastAPI
* SQLAlchemy
* Pydantic
* Alembic
* PostgreSQL

### Frontend

* React
* Vite
* Nginx

### Infraestrutura

* Docker
* Docker Compose
* Caddy
* PostgreSQL

### Estações

* ESP32-S3
* Arduino Framework
* PlatformIO
* Wi-Fi
* Bluetooth Low Energy (BLE)

### Aplicativo mobile

* React Native
* Expo
* Expo Router
* BLE

---

## Banco de dados

O PostgreSQL é utilizado para persistência dos dados.

As principais entidades são:

```text
devices
   │
   │ 1:N
   ▼
measurements
   │
   │ 1:1
   ▼
sensor_values
```

### `devices`

Armazena informações de cada estação, incluindo:

* identificador interno;
* hardware ID;
* nome;
* versão do firmware;
* estado da estação;
* localização;
* último contato;
* credencial de autenticação.

### `measurements`

Armazena informações associadas a cada aquisição, como:

* estação;
* timestamp da medição;
* horário de recebimento;
* localização associada à aquisição.

### `sensor_values`

Armazena os valores ambientais associados à medição.

---

## Identificação das estações

Cada ESP32 possui um identificador de hardware.

Durante o cadastro da estação, o servidor associa esse hardware a um identificador no formato:

```text
CASA-000001
CASA-000002
CASA-000003
...
```

Esse identificador é utilizado internamente pelo sistema.

O usuário trabalha principalmente com o **nome da estação**, configurado durante o cadastro.

---

## Autenticação das estações

Durante o primeiro cadastro, o backend gera uma credencial exclusiva para a estação.

A credencial original é enviada ao dispositivo e armazenada pelo ESP32.

O servidor não armazena diretamente a credencial original. É mantido apenas o valor necessário para sua validação.

As requisições de envio de medições precisam apresentar uma credencial válida correspondente à estação.

Isso impede que um dispositivo não autorizado envie medições utilizando apenas o `device_id` de outra estação.

---

## Configuração das estações

A configuração inicial é realizada pelo aplicativo mobile através de BLE.

O fluxo geral é:

```text
ESP32
  │
  │ BLE
  ▼
Aplicativo
  │
  ├── identifica o hardware
  ├── cadastra a estação no servidor
  ├── envia identidade e credencial ao ESP32
  └── configura Wi-Fi e servidor
```

Depois da configuração inicial, o ESP32 pode operar de maneira independente do aplicativo.

---

## Configuração do ambiente

Crie o arquivo `.env` na raiz do projeto.

Um exemplo está disponível em:

```text
.env.example
```

Configuração básica:

```env
POSTGRES_DB=casa_db
POSTGRES_USER=casa
POSTGRES_PASSWORD=change_me
```

> Não utilize a senha de exemplo em produção.

O arquivo `.env` contendo credenciais reais não deve ser versionado.

---

## Executando com Docker

É necessário ter Docker e Docker Compose instalados.

Na raiz do projeto:

```bash
docker compose up -d --build
```

Para verificar os containers:

```bash
docker compose ps
```

Para acompanhar os logs:

```bash
docker compose logs -f
```

Ou apenas o backend:

```bash
docker compose logs -f backend
```

---

## Acessando a aplicação

Com a configuração local atual, o Caddy é o ponto de entrada da aplicação.

Frontend:

```text
http://localhost
```

Health check da API:

```text
http://localhost/api/health
```

O retorno esperado é:

```json
{
  "status": "ok",
  "database": "connected"
}
```

A API também possui documentação automática disponibilizada pelo FastAPI.

---

## Rede Docker

Os serviços internos não precisam ser publicados diretamente para o host.

A comunicação ocorre através da rede criada pelo Docker Compose:

```text
Caddy
 ├── frontend:80
 └── backend:8000
          │
          └── db:5432
```

O Caddy é responsável por receber as requisições externas e encaminhá-las ao serviço correspondente.

As requisições iniciadas por `/api/` são encaminhadas para o backend.

---

## Migrações do banco

O projeto utiliza Alembic para controle de versão do esquema do banco de dados.

As migrations são aplicadas durante a inicialização do backend.

Também podem ser verificadas manualmente dentro do container:

```bash
docker compose exec backend alembic current
```

Para aplicar todas as migrations disponíveis:

```bash
docker compose exec backend alembic upgrade head
```

---

## Acessando o PostgreSQL

Mesmo sem publicar a porta do PostgreSQL para o host, o banco pode ser acessado diretamente pelo container:

```bash
docker compose exec db psql -U casa -d casa_db
```

Exemplo:

```sql
SELECT COUNT(*) FROM devices;

SELECT COUNT(*) FROM measurements;

SELECT COUNT(*) FROM sensor_values;
```

Para sair:

```text
\q
```

---

## Backup do banco de dados

Um backup em formato custom do PostgreSQL pode ser criado com:

```bash
docker compose exec -T db pg_dump \
  -U casa \
  -d casa_db \
  -Fc \
  > backups/casa_backup.dump
```

Para verificar o conteúdo:

```bash
docker compose exec -T db pg_restore --list \
  < backups/casa_backup.dump
```

Os backups não devem ser enviados ao Git.

---

## Parando a aplicação

Para interromper os containers:

```bash
docker compose down
```

Esse comando não remove o volume persistente do PostgreSQL.

> Não utilize `docker compose down -v` em um ambiente contendo dados que precisam ser preservados, pois a opção `-v` remove os volumes associados ao projeto.

---

## Estado atual

O sistema já possui um fluxo funcional completo de aquisição:

```text
Sensores
   ↓
ESP32
   ↓
Wi-Fi
   ↓
Caddy
   ↓
FastAPI
   ↓
PostgreSQL
   ↓
React
```

Já estão implementados:

* aquisição dos sensores ambientais;
* configuração do ESP32 por BLE;
* configuração de Wi-Fi pelo aplicativo;
* identificação do hardware;
* cadastro de novas estações;
* geração de identificadores CASA;
* autenticação individual das estações;
* armazenamento das medições no PostgreSQL;
* consulta de histórico;
* consulta da última medição;
* visualização das estações no frontend;
* filtros temporais e de quantidade de pontos;
* execução da infraestrutura com Docker Compose;
* migrations automáticas com Alembic;
* health checks;
* proxy reverso com Caddy;
* persistência do banco através de volume Docker.

---

## Próximas etapas

O projeto encontra-se em preparação para sua primeira validação com múltiplas estações.

Entre as próximas etapas estão:

* implantação da infraestrutura em servidor na nuvem;
* configuração de domínio e HTTPS;
* testes com seis estações simultâneas;
* reconexão automática após falhas de Wi-Fi;
* armazenamento temporário de medições durante indisponibilidade de rede;
* reenvio das medições pendentes;
* implementação do módulo GPS;
* backups automáticos do banco;
* monitoramento da infraestrutura;
* expansão gradual do número de estações.

---

## Repositórios relacionados

O ecossistema CASA também inclui projetos separados para:

* firmware do ESP32;
* aplicativo mobile de configuração;
* interface web de visualização.

Durante o desenvolvimento, versões desses componentes podem ser integradas ao repositório principal para implantação conjunta da infraestrutura.

---

## Projeto CASA

**Central de Acompanhamento de Saúde e Ambiente**

Sistema de monitoramento ambiental distribuído baseado em estações ESP32, aquisição multiparamétrica, comunicação sem fio, armazenamento centralizado e visualização web.
