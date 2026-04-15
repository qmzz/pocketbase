<script>
    import PocketBase from "pocketbase";
    import FullPage from "@/components/base/FullPage.svelte";
    import Field from "@/components/base/Field.svelte";

    const pb = new PocketBase("/");

    let searchKeyword = "";
    let supplierType = "";
    let status = "";
    let isLoading = false;
    let results = [];
    let totalCount = 0;
    let page = 1;
    const perPage = 20;

    const supplierTypes = ["", "生产商", "经销商", "服务商", "其他"];
    const statuses = ["", "潜在", "合作中", "暂停", "停用"];

    async function search(resetPage = true) {
        if (resetPage) {
            page = 1;
        }

        isLoading = true;

        try {
            const filter = buildFilter();
            const expand = "supplier_contacts";

            const response = await pb.collection("suppliers").getList(page, perPage, {
                filter,
                expand,
                sort: "-created",
            });

            results = response.items;
            totalCount = response.totalItems;
        } catch (err) {
            console.error("Search failed:", err);
            results = [];
            totalCount = 0;
        }

        isLoading = false;
    }

    function buildFilter() {
        const conditions = [];

        if (searchKeyword.trim()) {
            const keyword = searchKeyword.trim();
            conditions.push(
                `(${
                    `supplier_name ~ "${keyword}" || ` +
                    `supplier_code ~ "${keyword}" || ` +
                    `phone ~ "${keyword}" || ` +
                    `supplier_contacts.contact_name ~ "${keyword}" || ` +
                    `supplier_contacts.mobile ~ "${keyword}" || ` +
                    `supplier_contacts.wechat ~ "${keyword}"`
                })`
            );
        }

        if (supplierType) {
            conditions.push(`supplier_type = "${supplierType}"`);
        }

        if (status) {
            conditions.push(`status = "${status}"`);
        }

        return conditions.length > 0 ? conditions.join(" && ") : "";
    }

    function clearFilters() {
        searchKeyword = "";
        supplierType = "";
        status = "";
        results = [];
        totalCount = 0;
    }

    function goToPage(newPage) {
        if (newPage < 1 || newPage > Math.ceil(totalCount / perPage)) {
            return;
        }
        page = newPage;
        search(false);
    }

    function getTotalPages() {
        return Math.ceil(totalCount / perPage);
    }

    search();
</script>

<FullPage>
    <div class="page-header">
        <h1 class="page-title">供应商信息查询</h1>
        <a href="/_/#/login" class="admin-link">
            <i class="ri-login-box-line"></i>
            <span>后台入口</span>
        </a>
    </div>

    <div class="search-panel">
        <form class="search-form" on:submit|preventDefault={() => search(true)}>
            <Field class="form-field" name="keyword" let:uniqueId>
                <label for={uniqueId}>搜索关键词</label>
                <input
                    id={uniqueId}
                    type="text"
                    bind:value={searchKeyword}
                    placeholder="供应商名称 / 联系人 / 电话 / 微信号"
                />
            </Field>

            <Field class="form-field" name="supplierType" let:uniqueId>
                <label for={uniqueId}>供应商类型</label>
                <select id={uniqueId} bind:value={supplierType}>
                    {#each supplierTypes as type}
                        <option value={type}>{type || "全部"}</option>
                    {/each}
                </select>
            </Field>

            <Field class="form-field" name="status" let:uniqueId>
                <label for={uniqueId}>状态</label>
                <select id={uniqueId} bind:value={status}>
                    {#each statuses as s}
                        <option value={s}>{s || "全部"}</option>
                    {/each}
                </select>
            </Field>

            <div class="form-actions">
                <button
                    type="submit"
                    class="btn btn-lg"
                    class:btn-loading={isLoading}
                    disabled={isLoading}
                >
                    <i class="ri-search-line"></i>
                    <span class="txt">搜索</span>
                </button>
                <button
                    type="button"
                    class="btn btn-lg btn-transparent"
                    on:click={clearFilters}
                    disabled={isLoading}
                >
                    <i class="ri-close-line"></i>
                    <span class="txt">清空</span>
                </button>
            </div>
        </form>
    </div>

    {#if isLoading}
        <div class="results-loading txt-center">
            <span class="loader"></span>
            <p>加载中...</p>
        </div>
    {:else if results.length === 0}
        <div class="results-empty txt-center">
            <i class="ri-database-2-line"></i>
            <p>暂无数据</p>
        </div>
    {:else}
        <div class="results-info">
            共找到 <strong>{totalCount}</strong> 条记录
        </div>

        <div class="results-list">
            {#each results as supplier}
                <div class="result-card">
                    <div class="card-header">
                        <h5 class="supplier-name">{supplier.supplier_name}</h5>
                        <span class="label label-info">{supplier.supplier_type}</span>
                        <span class="label label-success">{supplier.status}</span>
                    </div>

                    <div class="card-body">
                        <div class="info-row">
                            <span class="info-label">供应商编码：</span>
                            <span class="info-value">{supplier.supplier_code}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">联系电话：</span>
                            <span class="info-value">{supplier.phone || "-"}</span>
                        </div>
                        {#if supplier.remark}
                            <div class="info-row">
                                <span class="info-label">备注：</span>
                                <span class="info-value">{supplier.remark}</span>
                            </div>
                        {/if}

                        {#if supplier.expand?.supplier_contacts?.length > 0}
                            <div class="contacts-section">
                                <h6>联系人信息</h6>
                                {#each supplier.expand.supplier_contacts as contact}
                                    <div class="contact-item" class:is-primary={contact.is_primary}>
                                        {#if contact.is_primary}
                                            <span class="primary-badge">主要</span>
                                        {/if}
                                        <div class="contact-details">
                                            <div class="contact-row">
                                                <span class="contact-label">姓名：</span>
                                                <span class="contact-value">{contact.contact_name}</span>
                                                <span class="contact-label m-l-3">职位：</span>
                                                <span class="contact-value">{contact.position || "-"}</span>
                                            </div>
                                            <div class="contact-row">
                                                <span class="contact-label">手机：</span>
                                                <span class="contact-value">{contact.mobile || "-"}</span>
                                                <span class="contact-label m-l-3">邮箱：</span>
                                                <span class="contact-value">{contact.email || "-"}</span>
                                            </div>
                                            <div class="contact-row">
                                                <span class="contact-label">微信：</span>
                                                <span class="contact-value">{contact.wechat || "-"}</span>
                                                {#if contact.remark}
                                                    <span class="contact-label m-l-3">备注：</span>
                                                    <span class="contact-value">{contact.remark}</span>
                                                {/if}
                                            </div>
                                        </div>
                                    </div>
                                {/each}
                            </div>
                        {/if}
                    </div>
                </div>
            {/each}
        </div>

        {#if getTotalPages() > 1}
            <div class="pagination">
                <button
                    type="button"
                    class="btn btn-sm btn-transparent"
                    disabled={page <= 1}
                    on:click={() => goToPage(page - 1)}
                >
                    <i class="ri-arrow-left-s-line"></i>
                    上一页
                </button>

                <span class="page-info">
                    第 {page} 页 / 共 {getTotalPages()} 页
                </span>

                <button
                    type="button"
                    class="btn btn-sm btn-transparent"
                    disabled={page >= getTotalPages()}
                    on:click={() => goToPage(page + 1)}
                >
                    下一页
                    <i class="ri-arrow-right-s-line"></i>
                </button>
            </div>
        {/if}
    {/if}
</FullPage>

<style>
    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        padding-bottom: 15px;
        border-bottom: 1px solid var(--borderColor);
    }

    .page-title {
        margin: 0;
        font-size: 20px;
    }

    .admin-link {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 8px 16px;
        background: var(--bodyBgColor);
        border-radius: 6px;
        text-decoration: none;
        color: var(--txtPrimaryColor);
        font-size: 14px;
        transition: background 0.2s;
    }

    .admin-link:hover {
        background: var(--txtHintColor);
        color: #fff;
    }

    .search-panel {
        max-width: 900px;
        margin: 0 auto 30px;
        padding: 20px;
        background: var(--bodyBgColor);
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    .search-form {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 15px;
    }

    .form-actions {
        grid-column: 1 / -1;
        display: flex;
        gap: 10px;
        justify-content: center;
        margin-top: 10px;
    }

    .results-loading,
    .results-empty {
        padding: 60px 20px;
        color: var(--txtHintColor);
    }

    .results-empty i {
        font-size: 48px;
        display: block;
        margin-bottom: 15px;
    }

    .results-info {
        max-width: 1200px;
        margin: 0 auto 20px;
        padding: 10px 20px;
        background: var(--bodyBgColor);
        border-radius: 6px;
    }

    .results-list {
        max-width: 1200px;
        margin: 0 auto;
    }

    .result-card {
        margin-bottom: 20px;
        padding: 20px;
        background: #fff;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
    }

    .card-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 15px;
        padding-bottom: 15px;
        border-bottom: 1px solid var(--borderColor);
    }

    .supplier-name {
        margin: 0;
        font-size: 18px;
        flex: 1;
    }

    .card-body {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .info-row {
        display: flex;
        gap: 8px;
    }

    .info-label {
        font-weight: 600;
        color: var(--txtHintColor);
        min-width: 80px;
    }

    .contacts-section {
        margin-top: 15px;
        padding-top: 15px;
        border-top: 1px solid var(--borderColor);
    }

    .contacts-section h6 {
        margin: 0 0 12px;
        color: var(--txtPrimaryColor);
        font-size: 14px;
    }

    .contact-item {
        padding: 12px;
        margin-bottom: 10px;
        background: var(--bodyBgColor);
        border-radius: 6px;
        position: relative;
    }

    .contact-item.is-primary {
        border-left: 3px solid var(--colorPrimary);
    }

    .primary-badge {
        position: absolute;
        top: 8px;
        right: 8px;
        font-size: 11px;
        padding: 2px 8px;
        background: var(--colorPrimary);
        color: #fff;
        border-radius: 10px;
    }

    .contact-details {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .contact-row {
        display: flex;
        gap: 6px;
        align-items: baseline;
        flex-wrap: wrap;
    }

    .contact-label {
        font-weight: 600;
        color: var(--txtHintColor);
    }

    .pagination {
        max-width: 600px;
        margin: 30px auto;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 20px;
    }

    .page-info {
        color: var(--txtHintColor);
        font-size: 14px;
    }
</style>
