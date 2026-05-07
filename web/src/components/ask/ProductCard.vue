<template>
  <div class="product-card" v-loading="loading">
    <template v-if="product">
      <div class="product-image-wrapper">
        <img
          v-if="product.image_url"
          :src="product.image_url"
          :alt="product.product_name"
          class="product-image"
          @error="onImageError"
        />
        <div v-else class="product-image-placeholder">
          {{ product.sku?.slice(0, 2) || '?' }}
        </div>
      </div>
      <div class="product-info">
        <div class="product-sku">SKU: {{ product.sku }}</div>
        <div class="product-name">{{ product.product_name || '未知商品' }}</div>
        <div class="product-category">
          <span v-if="product.category_l1">{{ product.category_l1 }}</span>
          <span v-if="product.category_l2"> &gt; {{ product.category_l2 }}</span>
          <span v-if="product.category_l3"> &gt; {{ product.category_l3 }}</span>
        </div>
        <div v-if="product.big_code" class="product-meta">
          <span class="meta-label">大编码</span>
          <span class="meta-value">{{ product.big_code }}</span>
        </div>
      </div>
    </template>
    <div v-else-if="!loading" class="product-empty">
      未找到商品信息
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { productDetailApi } from '@/api/productDetail'

const props = defineProps({
  sku: { type: String, required: true },
})

const product = ref(null)
const loading = ref(false)

watch(() => props.sku, async (sku) => {
  if (!sku) return
  loading.value = true
  product.value = null
  try {
    const res = await productDetailApi.getBySku(sku)
    const data = res.data || res
    if (data && data.length > 0) {
      product.value = data[0]
    }
  } catch (e) {
    console.warn('ProductCard fetch failed:', e)
  } finally {
    loading.value = false
  }
}, { immediate: true })

function onImageError(e) {
  e.target.style.display = 'none'
  const placeholder = e.target.parentElement.querySelector('.product-image-placeholder')
  if (placeholder) placeholder.style.display = 'flex'
  // create placeholder if not exists
  if (!placeholder) {
    const div = document.createElement('div')
    div.className = 'product-image-placeholder'
    div.textContent = props.sku?.slice(0, 2) || '?'
    e.target.parentElement.appendChild(div)
  }
}
</script>

<style scoped>
.product-card {
  display: flex;
  gap: 16px;
  padding: 16px;
  min-height: 120px;
}

.product-image-wrapper {
  flex-shrink: 0;
  width: 100px;
  height: 100px;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.product-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fff;
}

.product-image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #00B078 0%, #00A06B 100%);
  color: #fff;
  font-size: 24px;
  font-weight: 700;
  border-radius: 8px;
}

.product-info {
  flex: 1;
  min-width: 0;
}

.product-sku {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.product-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
  line-height: 1.4;
  word-break: break-all;
}

.product-category {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.product-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.meta-label {
  color: #999;
}

.meta-value {
  color: #333;
  font-weight: 500;
}

.product-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  color: #999;
  font-size: 13px;
}
</style>
