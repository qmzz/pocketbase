# supplier_import

通过 PocketBase REST API 批量导入供应商信息与联系人信息。

## 适用场景

当用户要求导入供应商信息、批量新增/更新 `suppliers` 与 `supplier_contacts`、从 JSON/CSV/Excel 整理后导入 PocketBase，或通过 API 写入供应商资料时，使用本 skill。

## 安全分离原则

本 skill 作为项目代码的一部分，**禁止提交真实 PocketBase 地址、账号、密码、token**。

真实连接信息只允许通过以下方式提供：

1. 当前 shell 环境变量
2. 本地未纳入 git 的 `.env` 文件，例如：`skills/supplier_import/.env`
3. CI/CD Secret

本仓库只保留占位示例：

```bash
PB_BASE_URL='http://127.0.0.1:8090'
PB_ADMIN_EMAIL='admin@example.com'
PB_ADMIN_PASSWORD='change-me'
# 或 PB_TOKEN='...'
```

`.env` 文件必须被 `.gitignore` 排除。

## 集合 schema

脚本默认适配以下集合。如果实际线上 schema 有变化，先查询 PocketBase schema，再调整字段映射。

### suppliers

- `supplier_code`：供应商编码，必填；输入为空时脚本自动生成 `SUP-xxxxxx`
- `supplier_name`：供应商名称，必填
- `supplier_type`：供应商类型，常见值：`生产商` / `经销商` / `服务商` / `其他`
- `status`：状态，常见值：`潜在` / `合作中` / `暂停` / `停用`；默认 `合作中`
- `phone`：联系电话
- `remark`：备注

### supplier_contacts

- `supplier`：关联供应商 record id，由脚本自动填充
- `contact_name`：联系人姓名
- `position`：职位
- `is_primary`：是否主联系人
- `mobile`：手机
- `email`：邮箱
- `wechat`：微信
- `remark`：联系人备注

## 认证方式

支持两种：

1. `PB_TOKEN`
2. `PB_ADMIN_EMAIL` + `PB_ADMIN_PASSWORD`

不要把真实密码写进仓库文件；只在本地环境变量、`.env` 或 Secret 中临时传入。

## 输入格式

### JSON

```json
[
  {
    "supplier_name": "示例供应商A",
    "supplier_code": "SUP-001",
    "supplier_type": "经销商",
    "status": "合作中",
    "phone": "13800000000",
    "remark": "示例备注",
    "contacts": [
      {
        "contact_name": "张三",
        "position": "销售经理",
        "mobile": "13900000000",
        "email": "zhangsan@example.com",
        "wechat": "zhangsanwx",
        "is_primary": true
      }
    ]
  }
]
```

### CSV

一行一个供应商联系人组合。字段：

```text
supplier_name,supplier_code,supplier_type,status,phone,remark,contact_name,position,mobile,email,wechat,is_primary
```

同一供应商多联系人可写多行，脚本会按 `supplier_code + supplier_name` 聚合。

## 常用命令

### 使用本地 `.env`

```bash
cp skills/supplier_import/.env.example skills/supplier_import/.env
# 编辑 .env，填入真实地址和凭据
set -a
. skills/supplier_import/.env
set +a
```

### 预检，不写入

```bash
python3 skills/supplier_import/scripts/import_suppliers.py \
  --base-url "$PB_BASE_URL" \
  --input suppliers.json \
  --dry-run
```

### 正式导入

```bash
python3 skills/supplier_import/scripts/import_suppliers.py \
  --base-url "$PB_BASE_URL" \
  --input suppliers.json
```

### 使用 token

```bash
PB_TOKEN='...' \
python3 skills/supplier_import/scripts/import_suppliers.py \
  --base-url "$PB_BASE_URL" \
  --input suppliers.json
```

## Upsert 规则

默认启用 upsert：

- 有 `supplier_code`：按 `supplier_code` 匹配供应商
- 无 `supplier_code`：按 `supplier_name` 匹配供应商，并自动生成编码
- 联系人按 `supplier + contact_name + mobile` 匹配；无 mobile 时按 `supplier + contact_name` 匹配

如需强制新增：

```bash
--no-upsert
```

## 安全要求

- 大批量导入前必须先 `--dry-run`。
- 正式导入真实业务数据前，应备份 PocketBase 数据库。
- 不要将账号密码、token、内网地址写入 git。
