# TLS certificates

Thư mục này **cố tình để trống** — không commit private key vào repo.

`Dockerfile.frontend` có `COPY nginx/certs /etc/nginx/certs`, nên thư mục
phải tồn tại (đó là lý do có `.gitkeep`), nhưng file `.pem` thì bạn tự đặt vào.

Cần đúng hai file:

- `fullchain.pem`
- `privkey.pem`

## Dev local — cert tự ký

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout nginx/certs/privkey.pem \
  -out nginx/certs/fullchain.pem \
  -subj "/CN=localhost"
```

Browser sẽ cảnh báo cert không tin cậy — bình thường với cert tự ký.
Nếu chỉ chạy HTTP ở local thì dùng `nginx.local.conf` và không cần cert.

## Production — Let's Encrypt

`deploy.sh` copy cert từ `/etc/letsencrypt/live/<domain>/` vào đây.
Sửa tên domain trong `deploy.sh` cho khớp với domain của bạn.
