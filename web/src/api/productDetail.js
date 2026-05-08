import request from './index'

export const productDetailApi = {
  getBySku(sku) {
    return request({
      url: '/product/details',
      method: 'post',
      data: { skus: [sku] },
    })
  },
}
