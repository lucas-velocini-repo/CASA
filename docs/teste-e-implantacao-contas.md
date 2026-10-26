# Passo a passo: testar e implantar contas no CASA

Este roteiro separa **computador de testes** e **VM de produção**. Os comandos locais funcionam em Ubuntu ou Windows com Git Bash e Docker Desktop em execução. Na VM, use o terminal Linux habitual do projeto. Troque os endereços e e-mails de exemplo pelos seus.

Não faça merge das PRs antes da homologação. Os testes devem usar dados fictícios e um banco novo. Não restaure o banco real no computador de testes e não aponte `TEST_DATABASE_URL` para produção: os testes automatizados apagam suas tabelas de teste.

## 1. Preparar uma cópia para testes

No computador de testes:

```bash
git clone --branch feature/user-accounts https://github.com/lucas-velocini-repo/CASA.git CASA-contas-teste
cd CASA-contas-teste
cp .env.teste.example .env.teste
```

Se já clonou essa branch, atualize com `git pull --ff-only` dentro da cópia de testes, depois de verificar `git status --short`.

Confira as ferramentas:

```bash
git --version
docker --version
docker compose version
```

O arquivo `compose.teste.yaml` é independente: não tem `container_name` fixo, publica somente a porta HTTP de testes e usa o volume do projeto `casa-teste`. **Não combine esse arquivo com `compose.yaml` usando dois `-f`.** Isso evita carregar os nomes, as portas ou o banco do Compose de produção.

## 2. Descobrir o IP do computador

Use `ipconfig` no Windows ou `hostname -I` no Ubuntu. Escolha o IPv4 da conexão Wi-Fi/Ethernet utilizada pelo celular, por exemplo `192.168.1.100`. Não use o IP de uma interface Docker, VPN ou `127.0.0.1` para o acesso do telefone.

Neste roteiro, o endereço de testes será:

```text
http://192.168.1.100:8080
```

Substitua o IP em todos os exemplos pelo IP real do computador. Use **esse mesmo endereço** também no navegador do computador: o login exige correspondência exata com `PUBLIC_APP_URL`.

## 3. Configurar o ambiente de testes

Gere uma chave de teste; o comando usa apenas a biblioteca padrão do Python dentro de um container:

```bash
docker run --rm python:3.12-slim python -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'
```

Edite `.env.teste` e preencha:

```dotenv
POSTGRES_DB=casa_teste
POSTGRES_USER=casa_teste
POSTGRES_PASSWORD=UMA_SENHA_SOMENTE_PARA_TESTES
PUBLIC_APP_URL=http://192.168.1.100:8080
AUTH_ENCRYPTION_KEY=COLE_A_CHAVE_GERADA
TEST_HTTP_PORT=8080

SMTP_HOST=SEU_SERVIDOR_SMTP
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=SEU_USUARIO_SMTP
SMTP_PASSWORD=SUA_CREDENCIAL_SMTP
SMTP_FROM=SEU_REMETENTE_AUTORIZADO
```

Pode reutilizar os parâmetros SMTP que você já validou para os alertas, desde que o provedor autorize o remetente informado. O destinatário dos alertas não é necessariamente o remetente SMTP. Para porta 465 com TLS direto, use `SMTP_SECURITY=ssl`.

Se uma senha contiver `$`, `#` ou espaços, use aspas simples no arquivo, por exemplo `SMTP_PASSWORD='valor'`. Não copie as credenciais do banco de produção. Os arquivos `.env.teste` e `.env` estão ignorados pelo Git.

## 4. Subir o ambiente separado

Para não repetir uma linha longa, defina esta função **somente neste terminal de testes**:

```bash
cteste() {
  docker compose --env-file .env.teste -p casa-teste -f compose.teste.yaml "$@"
}
```

Ela vale enquanto esse terminal estiver aberto. Execute-a sempre na pasta `CASA-contas-teste`.

```bash
cteste config --quiet
cteste up -d --build
cteste ps
```

O primeiro comando deve terminar sem erro e não imprime as credenciais. Aguarde `db` e `backend` ficarem saudáveis; `frontend`, `caddy` e `mail-worker` devem estar em execução.

Abra no navegador:

```text
http://192.168.1.100:8080
http://192.168.1.100:8080/api/health
```

O primeiro deve mostrar o login; o segundo, `status: ok` e `database: connected`. Abra o healthcheck também no celular, conectado à mesma rede. Se não abrir, confira IP, Wi-Fi e firewall das portas 8080 e, posteriormente, 8081. Não encaminhe essas portas no roteador para a internet.

Para consultar erros:

```bash
cteste logs --tail=100 backend caddy mail-worker
```

## 5. Criar o administrador de testes

```bash
cteste exec backend python -m app.cli create-admin --email SEU_EMAIL_REAL --name "Lucas — teste"
```

Informe uma senha de teste com 15 a 128 caracteres. O terminal não mostra a senha enquanto você digita. Se o Git Bash apresentar erro de terminal interativo, execute o comando completo com `winpty docker compose --env-file .env.teste -p casa-teste -f compose.teste.yaml exec backend python -m app.cli create-admin --email SEU_EMAIL_REAL --name "Lucas — teste"`.

Entre pelo site no endereço do IP. Configure a chave no seu aplicativo autenticador, informe o código e guarde os dez códigos de recuperação. Aguarde o próximo código do autenticador para entrar novamente: um código já usado não pode ser reutilizado, nem entre site e aplicativo.

Esse comando cria apenas o primeiro administrador. Outros administradores são convidados pelo painel.

## 6. Criar duas estações fictícias

```bash
cteste exec -T backend python -m app.demo_seed
```

O comando cria `DEMO Estação A` e `DEMO Estação B`, com 24 medições fictícias por estação e coordenadas de demonstração. Ele só executa em `CASA_ENV=development` e no banco `casa_teste`.

Atualize o site. O administrador deve ver as duas estações, o histórico, os gráficos e a exportação CSV. Se repetir o comando após uma execução concluída, os registros existentes são preservados.

As medições fictícias são geradas uma vez. É normal as estações DEMO aparecerem inativas depois de seis minutos: não há um ESP32 enviando novas leituras para elas. Se o teste atravessar a meia-noite, ajuste o filtro de período para incluir as leituras.

## 7. Testar convites, vínculos e permissões

Use dois e-mails seus ou aliases válidos que você realmente receba; os endereços precisam ser diferentes do administrador e entre si.

1. Em **Administração → Convidar uma pessoa**, convide a conta A como usuário.
2. Confirme a chegada do e-mail e abra o link. O computador/celular que abre o link precisa alcançar o IP local de testes.
3. Defina a senha e entre em janela anônima ou outro navegador. A conta A ainda deve ver **Nenhuma estação vinculada**.
4. No administrador, vincule somente `DEMO Estação A` à conta A. Escolha um início anterior às medições de demonstração e deixe o fim vazio.
5. Atualize a janela da conta A: ela deve ver somente a estação A, seus gráficos e seu CSV.
6. Convide a conta B, ative-a e vincule somente a estação B. Ela não pode ver a estação A.
7. Teste trocar o período do vínculo da conta A para permitir apenas parte do histórico. O histórico e o CSV devem conter somente esse intervalo. Se a localização atual estiver fora do intervalo, ela será ocultada.
8. Revogue o vínculo da conta A. Após nova consulta/atualização da página, ela não deve mais conseguir consultar a estação.
9. Recrie o vínculo e bloqueie a conta A. A próxima consulta deve pedir login. Reative a conta pelo administrador e confira novo login.
10. Use **Esqueci minha senha** na conta B; confira o e-mail, altere a senha e verifique que as sessões anteriores foram encerradas.
11. Tente reutilizar um convite aceito ou um link de recuperação consumido: o sistema deve recusá-lo.
12. No administrador, confira o registro de atividade e o estado da fila de e-mails.

| Acesso | Resultado esperado |
|---|---|
| Sem login, abrindo `/api/devices` | HTTP 401 |
| Administrador | Todas as estações |
| Conta A | Somente A, no período autorizado |
| Conta B | Somente B, no período autorizado |
| Conta sem vínculo | Lista vazia |
| Usuário comum, abrindo `/api/admin/users` | HTTP 403 |
| Usuário comum, pedindo histórico de estação alheia | HTTP 404 |

Para testar a última linha, conectado como conta A, abra o console do navegador e substitua o identificador abaixo pelo da estação B:

```javascript
fetch('/api/measurements/history?device_id=CASA-000002')
  .then(response => console.log(response.status));
```

Copie o identificador mostrado no administrador; ele pode diferir do exemplo. Revogar acesso não apaga dados que a pessoa já viu ou exportou.

## 8. Testar o aplicativo de celular

Para a rede local HTTP, use um **development build**, que roda com o servidor Metro. O perfil `preview` é um APK de distribuição e recusa HTTP nesta implementação. Expo Go não substitui o novo binário com BLE e SecureStore.

Em outro terminal, fora da pasta anterior:

```bash
git clone --branch feature/user-accounts https://github.com/lucas-velocini-repo/app-config-monitoramento-ambiental.git CASA-app-contas-teste
cd CASA-app-contas-teste
npm ci
```

Crie `.env.local` nessa pasta:

```dotenv
APP_VARIANT=development
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.100:8080/api
```

O endereço do app termina em `/api`; o `PUBLIC_APP_URL` do backend termina somente em `:8080`.

```bash
npx tsc --noEmit
npm run lint
npx eas-cli login
npx eas-cli build --platform android --profile development
```

Use a conta Expo/EAS já utilizada pelo projeto. Instale no telefone o APK de desenvolvimento gerado. A variante de desenvolvimento usa o pacote separado `.dev`, permitindo manter o aplicativo atual instalado.

Depois, na pasta do aplicativo:

```bash
npx expo start --dev-client --lan
```

Mantenha esse terminal aberto. Abra o aplicativo de desenvolvimento e conecte-o ao servidor Metro/QR exibido. Celular e computador devem estar na mesma rede. Quando alterar `.env.local`, reinicie o Metro.

Teste login com usuário comum: deve aparecer somente sua lista de estações e o botão para abrir os gráficos no site. O navegador tem sessão própria e pode pedir login. As telas de configuração devem ficar indisponíveis para essa conta.

Entre como administrador usando um novo código TOTP. As telas BLE devem ficar disponíveis. Teste também sair da conta e o retorno após colocar o app em segundo plano. Após bloquear uma conta pelo site, feche/reabra o app ou leve-o novamente ao primeiro plano para disparar a validação da sessão.

## 9. Testar uma estação real de laboratório

Use uma placa reserva não provisionada com o firmware atual. Não apague identidade ou token de uma estação de produção para realizar este teste.

1. Entre no app de desenvolvimento como administrador.
2. Conecte à placa por BLE, cadastre-a e configure o Wi-Fi.
3. A rota de envio da estação deve ser `http://192.168.1.100:8080/api/measurements`.
4. Confira a nova estação e as primeiras medições no site de testes.
5. Vincule-a a uma conta comum e confira a visualização.
6. Teste a troca de Wi-Fi e a reconexão.
7. Se houver uma interrupção antes de gravar a identidade no ESP32, reconecte e retome o cadastro. Ele não deve duplicar a estação.
8. Para testar a fila offline, pare **somente o backend de testes**, aguarde uma ou duas aquisições e inicie-o novamente:

   ```bash
   cteste stop backend
   cteste start backend
   ```

   Aguarde as aquisições antes de executar `start`; não copie e cole as duas linhas sem esperar. As medições pendentes devem chegar sem duplicar registros.

O login do app oficial não protege o firmware contra comandos de outro cliente BLE. Esse é um limite conhecido desta entrega e não deve ser interpretado como falha do isolamento da API.

## 10. Aprovar as alterações e preparar o APK de distribuição

Após aprovar os testes:

- CASA: PR #5 → **Ready for review** → conferir checks → merge na `main`.
- Aplicativo: PR #1 → **Ready for review** → conferir alterações → merge na `id-hardware`.

Para evitar carregar o IP/variante de desenvolvimento da pasta de testes, use uma **nova cópia limpa** para o APK de distribuição:

```bash
git clone --branch id-hardware https://github.com/lucas-velocini-repo/app-config-monitoramento-ambiental.git CASA-app-contas-producao
cd CASA-app-contas-producao
npm ci
npx eas-cli build --platform android --profile preview
```

O perfil `preview` já aponta para `https://t2phealth.com.br/api` e gera APK. Se o endereço real do CASA for diferente, corrija esse perfil antes da compilação. Não crie `.env.local` de desenvolvimento nessa cópia.

Deixe o APK pronto para instalar. O login desse APK só funcionará quando o backend de produção estiver atualizado. As contas e o administrador de testes não serão transferidos para produção.

## 11. Fazer backup na VM, ainda com a versão antiga

Na VM, antes de atualizar o código:

```bash
cd /opt/CASA
git status --short
docker compose ps
```

Confira que está na instalação correta e que não há alterações locais a preservar. Não use `git reset --hard` para resolver diferenças. Se a implantação usa um nome de projeto Compose específico, mantenha exatamente esse nome em todos os comandos de produção.

Crie uma cópia imediata em uma pasta privada, fora do repositório:

```bash
umask 077
backup_contas_dir="$HOME/casa-pre-contas-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_contas_dir"
git rev-parse HEAD > "$backup_contas_dir/commit.txt"
cp .env "$backup_contas_dir/env.anterior"
cp compose.yaml "$backup_contas_dir/compose.anterior.yaml"
cp infra/Caddyfile "$backup_contas_dir/Caddyfile.anterior"
crontab -l > "$backup_contas_dir/crontab.txt"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_contas_dir/banco.dump"
test -s "$backup_contas_dir/banco.dump"
docker compose exec -T db pg_restore --list < "$backup_contas_dir/banco.dump"
```

Só prossiga se o dump terminou sem erro, o arquivo não está vazio e a listagem do `pg_restore` funciona. O nome da pasta fica na variável `backup_contas_dir` neste terminal; se abrir outro, use o caminho real da pasta criada.

Esse backup local não substitui o backup externo já configurado. Execute também a rotina habitual que envia ao Drive e confirme a disponibilidade do backup. A listagem do dump verifica o formato; um ensaio completo de restauração deve usar banco separado, sem substituir produção.

Registre a situação do banco antes da mudança:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) AS estacoes FROM devices; SELECT COUNT(*) AS medicoes FROM measurements; SELECT MAX(received_at) AS ultimo_recebimento FROM measurements;"'
```

## 12. Atualizar a VM e completar o `.env`

Depois do merge das PRs:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
```

Edite o `.env` existente, preservando `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD`. Gere uma **nova chave para produção**, diferente da chave de testes, com o mesmo comando Docker do passo 3.

Acrescente/preencha:

```dotenv
CASA_ENV=production
PUBLIC_APP_URL=https://t2phealth.com.br
CASA_DOMAIN=t2phealth.com.br
AUTH_ENCRYPTION_KEY=CHAVE_ESTAVEL_DE_PRODUCAO
CADDY_CONFIG_PATH=./infra/Caddyfile.http-ingestion

SMTP_HOST=SEU_SERVIDOR_SMTP
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=SEU_USUARIO_SMTP
SMTP_PASSWORD=SUA_CREDENCIAL_SMTP
SMTP_FROM=SEU_REMETENTE_AUTORIZADO
```

Não copie todo o `.env.teste` para a VM. Não regenere a chave Fernet depois de começar a usar as contas; ela será necessária para abrir os segredos TOTP e os e-mails pendentes. Preserve-a com segurança no procedimento de recuperação da configuração.

O arquivo transitório aceita as rotas de ingestão HTTP por domínio **e por IP**, enquanto direciona o site para HTTPS. Ele não altera o endereço já salvo nos ESP32. Os envios que continuam em HTTP ainda não têm proteção TLS no transporte; a migração do firmware para HTTPS verificado é uma etapa separada.

## 13. Conferir DNS e Cloudflare antes da troca

O domínio informado precisa apontar para a VM e as portas TCP 80/443 precisam chegar ao Caddy. Use o endereço real da interface em `PUBLIC_APP_URL`; não inclua `/api`.

Se o site usa proxy da Cloudflare:

1. Anote o estado atual do registro DNS do site e do modo SSL/TLS.
2. O destino final deve ser **Full (strict)**, com certificado válido no Caddy. O modo **Flexible**, combinado com o redirecionamento HTTP→HTTPS da origem, pode causar loop.
3. Se ainda estiver em Flexible, faça a transição em uma janela de manutenção. Uma opção é deixar **temporariamente somente o registro DNS do site** em DNS only, iniciar o Caddy atualizado, validar o HTTPS da origem, selecionar Full (strict) e reativar o proxy se ele era usado antes.
4. Não adicione um redirecionamento global novo de HTTP para HTTPS na Cloudflare durante a transição das estações. Se uma estação usa HTTP pelo domínio e já existem regras de redirecionamento na borda, elas também precisam permitir as duas rotas de ingestão; o Caddy não consegue desfazer um redirecionamento que a Cloudflare já enviou.

Se não conseguir validar o certificado ou identificar esse caminho, mantenha a mudança de produção pendente. O ambiente local já permite testar as contas sem alterar DNS.

## 14. Compilar, migrar e criar o primeiro administrador real

Na pasta `/opt/CASA`, com o `.env` completo:

```bash
docker compose config --quiet
docker compose build backend frontend mail-worker
docker compose run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose run --rm backend alembic upgrade head
```

A migração `c621accounts01` acrescenta tabelas. Não exclui as estações existentes, medições ou hashes de tokens.

Crie o administrador de produção, com seu e-mail real e uma senha diferente da de testes:

```bash
docker compose run --rm backend python -m app.cli create-admin --email SEU_EMAIL_REAL --name "Lucas"
```

Não execute `app.demo_seed` na VM. Ele é bloqueado em produção; as estações reais já estão cadastradas.

Inicie a versão atualizada:

```bash
docker compose up -d
docker compose ps
docker compose logs --tail=100 backend mail-worker caddy
```

Aguarde os serviços ficarem disponíveis. Confira:

```bash
curl -i https://t2phealth.com.br/api/health
curl -i https://t2phealth.com.br/api/devices
```

Esperado: healthcheck HTTP 200 com banco conectado; listagem anônima HTTP 401. Não use `curl -k` para considerar o HTTPS validado.

Para verificar o certificado diretamente na origem, substitua `IP_DA_VM` pelo IP público real:

```bash
curl --resolve t2phealth.com.br:443:IP_DA_VM https://t2phealth.com.br/api/health
```

Se alterou o DNS/proxy no passo 13, finalize a transição para Full (strict) somente após a origem apresentar certificado válido.

## 15. Confirmar que a coleta continua funcionando

Faça uma requisição de ingestão **sem token**, sem seguir redirecionamentos:

```bash
curl -i -X POST http://IP_DA_VM/api/measurements -H 'Content-Type: application/json' --data '{"device_id":"TESTE-SEM-TOKEN","timestamp":1780000000,"pm":{},"nc":{}}'
```

O resultado esperado é **401**, sem `Location` de redirecionamento. Nenhuma medição será gravada. Se as estações usam o domínio por HTTP, repita com `http://t2phealth.com.br/api/measurements`; esse caminho também deve chegar à autenticação sem 301/302/307/308.

Espere um ou dois intervalos reais de aquisição e repita a consulta de contagem/último recebimento do passo 11. O total de estações deve ser preservado; o total de medições deve ser igual ou maior; o último recebimento deve avançar conforme as estações enviarem.

A localização é enviada em outra periodicidade; não espere uma nova data GPS a cada medição ambiental. Verifique a atualização de localização no próximo envio programado ou em uma estação de laboratório.

## 16. Habilitar as contas reais e o aplicativo

1. Abra o site por HTTPS, entre com o administrador real, configure TOTP e guarde os códigos de recuperação.
2. Confirme que as estações antigas e seus históricos aparecem para o administrador.
3. Convide primeiro uma conta comum da equipe para validar a entrega real do e-mail e a recuperação de senha.
4. Vincule uma estação e confira o isolamento em outro navegador.
5. Cadastre os demais usuários e atribua os períodos de acesso conforme a instalação/residência correspondente. Não libere automaticamente o histórico de uma residência anterior.
6. Instale o APK de distribuição preparado no passo 10. Entre com a conta real e confirme a lista vinculada e o acesso administrativo.
7. Confira o backup externo, os alertas já configurados e uma nova cópia da configuração com a chave Fernet preservada com segurança.

O APK antigo não cadastra novas estações depois desta mudança porque não envia uma sessão de usuário. Ele não interfere no envio das estações já provisionadas.

## 17. Encerrar os testes e lidar com falhas

Para parar somente o ambiente de testes, na pasta de testes e com a função `cteste` definida:

```bash
cteste down
```

Isso preserva o volume de testes. Não use `down -v` na produção.

| Sintoma | O que conferir |
|---|---|
| Origem não autorizada | Endereço aberto no navegador exatamente igual a `PUBLIC_APP_URL`, incluindo IP/domínio, protocolo e porta |
| E-mail não chega | `mail-worker`, estado da fila, remetente autorizado, SMTP/porta/TLS e spam; após corrigir, reenvie o convite |
| App de distribuição recusa HTTP | Use o development build no teste local ou um servidor de homologação com HTTPS |
| Telefone não acessa teste | Mesma rede, IP correto, firewall 8080/8081, healthcheck acessível no navegador do telefone |
| Código TOTP recusado | Relógio automático do telefone e código novo, ainda não usado em outro login |
| Estações param após Caddy | Arquivo transitório, Host/IP usado pelos ESP32 e ausência de redirecionamentos nas rotas de ingestão |
| Loop HTTPS/Cloudflare | Modo Flexible ou regras de redirecionamento; confirme a origem e o modo Full (strict) |
| Conta comum não vê localização | Data da localização dentro do período autorizado pelo vínculo |

Se houver falha após a implantação, preserve o banco e consulte os logs. **Não restaure o dump por cima do banco em uso e não execute downgrade de migração para resolver uma falha de interface.** Voltar à versão anterior do frontend/backend reabre as consultas públicas; em caso de emergência, mantenha temporariamente o acesso web indisponível enquanto corrige, preservando a ingestão das estações e os dados já coletados.
