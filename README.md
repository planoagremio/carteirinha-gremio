# Controle de Acesso do Clube

Aplicação web single-file (`controle_acesso_clube.html`) para controlar a entrada de sócios/pessoas autorizadas num clube, via carteirinha digital com QR code. Não há controle de saída nem catraca — apenas registro de entrada.

## Stack

- HTML + CSS + JavaScript puro (sem build, sem framework).
- Bibliotecas via CDN (carregadas no `<head>`):
  - [`qrcodejs`](https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js) — geração dos QR codes das carteirinhas.
  - [`jsQR`](https://cdnjs.cloudflare.com/ajax/libs/jsQR/1.4.0/jsQR.js) — leitura do QR code via câmera.
- Persistência de dados via `window.storage` (armazenamento chave-valor **compartilhado**, ou seja, visível para qualquer pessoa que abra este mesmo artefato/link). Não usa `localStorage`/`sessionStorage`.

## Estrutura de dados (storage)

| Chave              | Conteúdo                                                              |
|---------------------|-------------------------------------------------------------------------|
| `club-members`      | Array JSON com todos os sócios: `{ id, nome, doc, foto (base64), criadoEm }` |
| `club-checkins`      | Array JSON com o histórico de entradas: `{ memberId, nome, date, time, ts }` |
| `club-auth`          | `{ passHash }` — hash SHA-256 da senha de acesso ao app                |

Todas as chaves são gravadas com `shared: true`, então persistem entre sessões e dispositivos diferentes (não dependem do navegador de quem está usando).

## Funcionalidades (abas)

1. **Cadastro** — cadastro manual de sócios (nome, documento opcional, foto). A foto é redimensionada no cliente antes de salvar (thumbnail ~160x160, JPEG). Lista de sócios com opção de remover.
2. **Carteirinha** — seleciona um sócio cadastrado e mostra um cartão digital (estilo ticket) com foto, nome, documento e QR code (o QR contém apenas o `id` interno do sócio). Botão para baixar o cartão como imagem PNG (gerado via `<canvas>`).
3. **Leitor** — ativa a câmera (`getUserMedia`) do celular/tablet da recepção, faz leitura contínua de QR code via `jsQR`. Ao reconhecer um sócio válido, mostra foto + nome (conferência visual) e grava a entrada com data/hora. Evita duplicar entrada do mesmo sócio no mesmo dia (mostra aviso, mas não bloqueia).
4. **Presença** — lista as entradas registradas, filtrável por data (`<input type="date">`).

## Autenticação

- Tela de bloqueio (`#auth-screen`) cobre todo o app até login.
- Primeiro acesso: cria uma senha (mín. 4 caracteres), salva como hash SHA-256 (`crypto.subtle.digest`) em `club-auth`.
- Acessos seguintes: pede a senha e compara o hash.
- Estado "desbloqueado" fica só em memória (variável JS) — recarregar a página exige login de novo, já que não é permitido usar `localStorage`/`sessionStorage` em artifacts.
- Botão **Bloquear** no cabeçalho: relock manual sem precisar recarregar.
- **Trocar senha de acesso** (rodapé): pede senha atual + nova senha (2x) via `prompt()`.

> ⚠️ Isso é uma trava de uso prático (impede acesso casual), não segurança de nível produção/bancário — é tudo client-side, sem backend.

## Escudo do clube (placeholder configurável)

Por regra de direito de marca, **não foi inserido nenhum escudo/logo oficial** no código — nem gerado, nem buscado, nem reproduzido. Em vez disso, existe um placeholder configurável:

```js
// dentro da tag <script>, perto do topo:
const CLUB_LOGO_URL = '';
```

- Deixe como `''` para manter o emblema genérico tricolor (placeholder visual, sem nenhuma marca).
- Preencha com o caminho/URL de um arquivo de imagem que você mesmo forneça (ex.: `'escudo.png'` na mesma pasta do HTML, uma URL completa, ou uma data URI base64) para que o escudo real apareça.
- Não é necessário alterar mais nada no layout — o mesmo valor é usado automaticamente em três lugares:
  1. Círculo no cabeçalho (`#header-logo`).
  2. Badge circular no canto da carteirinha, na tela (`#ticket-logo` dentro de `#ticket-badge`).
  3. Badge equivalente desenhado na imagem PNG baixada da carteirinha (função `drawBadge` dentro do handler do botão "Baixar carteirinha").
- Se o arquivo não carregar (caminho errado, por exemplo), o app simplesmente não mostra nada ali — não quebra o layout.

## Limitações conhecidas / próximos passos possíveis

- [x] Senha de acesso (feito)
- [ ] Controle de plano/mensalidade (sócio ativo vs. vencido)
- [ ] Exportar presença em Excel/CSV
- [ ] Cadastro em lote (importar planilha em vez de um por um)
- [ ] QR code com validação mais forte (hoje é só o `id`; print de tela de terceiros funciona — mitigado hoje só pela conferência visual da foto na recepção)

## Como rodar

Basta abrir o `controle_acesso_clube.html` direto no navegador (ou hospedar como página estática). Não precisa de servidor, build step nem `npm install`.
