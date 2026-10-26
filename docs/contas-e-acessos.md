# Contas, acesso às estações e implantação

Implementação iniciada a partir do CASA `40d31ad` e do aplicativo `id-hardware` em `ef92866`. O firmware `f721823` continua enviando medições e localização com o token de cada estação. Esta atualização não altera o intervalo de aquisição nem grava contas no ESP32.

Para executar o teste e a implantação com comandos completos, siga o [roteiro operacional](teste-e-implantacao-contas.md).

## Fluxo de uso

1. A equipe cria o primeiro administrador na VM. No primeiro login web ele configura TOTP e guarda os dez códigos de recuperação.
2. Administradores entram em **Administração**, convidam pessoas por nome e e-mail e vinculam suas estações. Convites pendentes já podem receber vínculos.
3. A pessoa abre o convite de e-mail, cria uma senha de 15 a 128 caracteres e entra no site ou no aplicativo. O administrador nunca define ou recebe essa senha.
4. Cada pessoa vê somente as estações vinculadas e as medições do período autorizado. Uma conta sem vínculos recebe uma lista vazia.
5. No aplicativo, administradores podem instalar estações; usuários comuns consultam a lista vinculada e abrem o site para gráficos. O site mantém sessão própria: abrir pelo aplicativo pode exigir login no navegador.

**Cadastro público não está habilitado.** Para convidar outro administrador, selecione esse perfil no convite. Administradores devem usar segundo fator; uma sessão de configuração MFA não pode consultar dados ou executar ações administrativas.

## Regras de acesso e histórico

- O perfil `admin` consulta todas as estações; `user` depende de vínculo ativo na tabela `device_access`.
- Um vínculo admite `data_from` (obrigatório e inclusivo) e `data_until` (opcional e exclusivo). As datas são armazenadas com timezone; o formulário administrativo usa o fuso do dispositivo de quem preenche.
- Se a estação mudar de residência, encerre/substitua os vínculos e defina o início da nova instalação. Nunca conceda o histórico da residência anterior por conveniência.
- Os limites usam o horário da **aquisição**, inclusive para medições que chegam depois pela fila offline.
- Salvar outro período para a mesma pessoa e estação revoga o vínculo anterior e cria um registro novo. A primeira versão permite um período ativo por par pessoa/estação; não oferece múltiplos intervalos simultâneos para o mesmo par.
- Coordenadas atuais e última comunicação são omitidas quando estão fora do período autorizado. O identificador de hardware não é exposto a usuários comuns.
- Revogar remove o acesso em novas consultas. Dados já vistos, copiados ou exportados não podem ser recuperados do computador do usuário.
- Bloquear uma **conta** encerra suas sessões e invalida links pendentes; não bloqueia o ESP32. Desativar uma **estação** recusa novas medições e pode aumentar sua fila local.
- Alterações de perfil encerram as sessões da conta. Não é permitido remover/bloquear o próprio administrador nem deixar o sistema sem administrador ativo.

## Sessões e credenciais

Senhas usam Argon2id com `pwdlib`. Tokens de sessão e de convite/recuperação são aleatórios e armazenados por SHA-256; esse hash rápido é apropriado para tokens de alta entropia, e não é usado para senhas.

Sessões web duram 12 horas, com cookie `__Host-casa_session` (HttpOnly, Secure, SameSite=Lax). Requisições de escrita pelo navegador exigem origem exata e token CSRF. Sessões mobile duram 7 dias e usam Bearer token guardado em Expo SecureStore; não são aceitas como cookies web. Não há renovação silenciosa nesta versão: após expirar, a pessoa entra novamente. Sessões são revogadas em logout, bloqueio, alteração de perfil e recuperação de senha.

Convites duram 48 horas; links de redefinição, 30 minutos. Links funcionam uma vez e o token é colocado no fragmento da URL, removido da barra pelo frontend antes de fazer requisições. O backend usa respostas genéricas na recuperação e limites de tentativas persistidos no PostgreSQL. TOTP e fila de e-mails são criptografados com Fernet; os códigos de recuperação de MFA ficam somente como hashes. Códigos TOTP e de recuperação não podem ser reutilizados.

## Variáveis novas

Complete o `.env` a partir de `.env.example`, preservando as credenciais atuais do banco. Não sobrescreva o `.env` da VM com o exemplo.

| Variável | Uso |
|---|---|
| `CASA_ENV=production` | Rejeita configuração sem HTTPS e chave Fernet |
| `PUBLIC_APP_URL=https://t2phealth.com.br` | Origem exata do site, sem barra final, caminho `/api` ou outros caminhos |
| `CASA_DOMAIN=t2phealth.com.br` | Host atendido pelo Caddy |
| `AUTH_ENCRYPTION_KEY` | Chave Fernet estável, igual no backend e no worker |
| `SMTP_HOST`, `SMTP_PORT` | Servidor SMTP e porta do remetente validado |
| `SMTP_SECURITY` | `starttls` (normalmente 587) ou `ssl` (normalmente 465) |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Credenciais do provedor de envio |
| `SMTP_FROM` | Remetente autorizado no provedor |
| `CADDY_CONFIG_PATH` | Arquivo Caddy escolhido para a implantação |

Gere a chave **uma única vez**, em um terminal privado, com a biblioteca instalada:

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Guarde a chave com segurança e mantenha uma cópia protegida para recuperação. Não envie a chave ao repositório ou a tickets. Não a regenere em reinícios: sem ela não é possível abrir os segredos TOTP e os e-mails pendentes. Uma troca de chave exige um procedimento de migração dos dados criptografados.

O serviço `mail-worker` lê a fila transacional no mesmo PostgreSQL, tenta novamente após falhas e recupera tarefas interrompidas por reinício. Depois de enviado, o conteúdo é apagado da fila. Após dez tentativas o envio fica como `failed`; a equipe pode reenviar o convite pelo painel. O painel mostra estado e tentativas, sem mostrar links ou conteúdo. A entrega usa a semântica de pelo menos uma vez: uma queda após o SMTP aceitar pode resultar em e-mail duplicado com o mesmo link.

## HTTPS e compatibilidade com as estações existentes

O `infra/Caddyfile` principal serve HTTPS e deixa o Caddy redirecionar HTTP. **Não o ative em produção antes de validar o envio HTTPS em cada ESP32.** O firmware atual usa `HTTPClient` sem configurar explicitamente a confiança dos certificados; a configuração de HTTPS do navegador não prova que o ESP32 está pronto.

Para testar as contas preservando estações ainda configuradas para HTTP, seja por domínio ou IP, use temporariamente:

```dotenv
CADDY_CONFIG_PATH=./infra/Caddyfile.http-ingestion
```

Nesse arquivo, HTTP é aceito apenas para `POST /api/measurements` e `PATCH /api/devices/location`. Site, contas e cadastro seguem para HTTPS. **Os tokens e os dados dos ESP32 que continuam em HTTP permanecem sem proteção TLS no transporte.** Essa compatibilidade não é uma solução final para a segurança do transporte das estações. Quando todos os ESP32 estiverem validados com HTTPS e verificação de certificado, selecione o arquivo principal e retire a exceção.

O host deve resolver para o serviço correto e permitir a validação de certificado pelo Caddy. Se houver proxy Cloudflare na frente, verifique também seu modo TLS e o caminho até a origem. Não presuma que o endereço público já fornecer HTTPS significa que a conexão até a VM está protegida. Cookies `Secure` exigem HTTPS no navegador.

Para desenvolvimento local, use `CASA_ENV=development`, uma origem HTTP exata em `PUBLIC_APP_URL` e `infra/Caddyfile.dev`. Ao usar Vite na porta 5173, essa deve ser a origem configurada no backend. Credenciais de produção não devem ser usadas no ambiente de desenvolvimento.

## Instalação coordenada, inicialmente em homologação

Esta mudança fecha as consultas anônimas e o cadastro anônimo de estações. O aplicativo antigo continuará incapaz de cadastrar novas estações após a mudança; as estações já provisionadas continuam enviando dados.

1. Compile e teste o novo APK antes da mudança do servidor. Não faça o merge/deploy do CASA esperando cadastrar estações com o APK anterior.
2. Faça um backup do PostgreSQL e preserve a configuração operacional atual, incluindo Caddyfile e rotinas de backup/alertas. Registre o commit atual. Teste a restauração em um banco separado.
3. Atualize o código aprovado e complete as variáveis novas no `.env`. Decida o arquivo Caddy de acordo com o transporte real dos ESP32.
4. Compile as imagens:

   ```bash
   docker compose build backend frontend mail-worker
   ```

5. Aplique a migração em uma janela acompanhada, mantendo o banco atual:

   ```bash
   docker compose run --rm backend alembic upgrade head
   ```

   A migração `c621accounts01` cria tabelas novas e não apaga estações, medições ou tokens. Nunca execute `docker compose down -v`.

6. Crie o primeiro administrador em terminal interativo. A senha é solicitada sem eco:

   ```bash
   docker compose run --rm backend python -m app.cli create-admin --email SEU_EMAIL --name "SEU_NOME"
   ```

   Esse comando só permite o primeiro administrador. Os demais devem ser convidados pelo painel.

7. Suba os serviços:

   ```bash
   docker compose up -d --build
   docker compose ps
   docker compose logs --tail=100 backend mail-worker caddy
   ```

8. Entre no site por HTTPS, configure o autenticador e guarde os códigos de recuperação. Para entrar logo após a configuração, espere o autenticador gerar o próximo código; o código já usado na ativação não pode ser reutilizado.
9. Convide uma conta de teste, confirme a entrega do e-mail e crie vínculos com períodos adequados. Teste o acesso comum, a recuperação de senha e a revogação antes de convidar os participantes.
10. Verifique recebimento de medições e de localização das estações reais, o APK novo, backup e alertas. O healthcheck permanece sem exigir conta e não fornece medições.

Se houver necessidade de rollback de aplicação, mantenha as tabelas novas e investigue a falha. **Voltar ao frontend/backend anterior reabre a visualização pública**, portanto não é um rollback seguro para dados que já devam estar restritos. Não execute downgrade de banco para solucionar falhas de interface; ele remove contas e vínculos. Não remova volumes.

## Recuperação administrativa

Se os dez códigos de recuperação forem perdidos junto com o autenticador, uma pessoa autorizada com acesso à VM pode executar:

```bash
docker compose exec backend python -m app.cli reset-mfa --email EMAIL_DA_CONTA
```

O comando pede confirmação, registra o evento, encerra sessões e obriga nova configuração MFA no próximo login. Não existe uma rota pública para desativar o segundo fator.

O painel também oferece recuperação de **cadastro pendente** da estação. Ela funciona apenas para provisionamentos desta versão ainda não confirmados e sem medições. Não troca o token de uma estação já em operação. O cadastro pendente pode ser retomado pelo app por até 24 horas; depois disso, um administrador precisa reiniciá-lo explicitamente. O primeiro envio de medições ou a confirmação pelo app encerra o estado pendente e apaga a cópia criptografada da credencial.

## Limite desta entrega: configuração por Bluetooth

O login protege as telas e requisições do aplicativo oficial. **O firmware atual não autentica os comandos BLE por conta de usuário.** Outro cliente Bluetooth ainda pode enviar comandos de configuração. A proteção física exige uma atualização separada do firmware, por exemplo uma janela de configuração por ação física e uma credencial própria de configuração. Os testes desta entrega não afirmam proteção completa do BLE.

## Validação local

Backend:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=. pytest -q
```

Os testes usam SQLite por padrão. Para repetir a suíte de contas em um PostgreSQL **descartável e exclusivo de testes**, defina `TEST_DATABASE_URL`; o fixture apaga e recria as tabelas. Nunca aponte essa variável para o banco da VM.

Frontend:

```bash
cd frontend
npm ci
npm test
npm run lint
npm run build
```

Além dos testes automatizados, valide com duas contas comuns diferentes, um administrador, uma conta sem vínculos e pelo menos uma estação real. O teste de concorrência e o ensaio final de Docker/PostgreSQL/SMTP devem ocorrer em homologação antes da implantação no servidor do projeto.
