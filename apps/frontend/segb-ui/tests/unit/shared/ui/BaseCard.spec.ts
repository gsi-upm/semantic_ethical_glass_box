import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import BaseCard from '@/shared/ui/BaseCard.vue'

describe('BaseCard', () => {
  it('renders title, subtitle, content and actions slot', () => {
    const wrapper = mount(BaseCard, {
      props: {
        title: 'System Logs',
        subtitle: 'Last 200 entries',
      },
      slots: {
        default: '<p>Body content</p>',
        actions: '<button type="button">Refresh</button>',
      },
    })

    expect(wrapper.find('.title').text()).toBe('System Logs')
    expect(wrapper.find('.subtitle').text()).toBe('Last 200 entries')
    expect(wrapper.text()).toContain('Body content')
    expect(wrapper.find('.actions button').text()).toBe('Refresh')
  })

  it('hides header when no title or subtitle is provided', () => {
    const wrapper = mount(BaseCard, {
      slots: {
        default: '<p>Only body</p>',
      },
    })

    expect(wrapper.find('header').exists()).toBe(false)
    expect(wrapper.text()).toContain('Only body')
  })
})
