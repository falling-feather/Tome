import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const STORAGE_KEY = 'inkless-lang';

const resources = {
  'zh-CN': {
    translation: {
      app: {
        title: '不存在之书',
        subtitle: 'Inkless',
      },
      nav: {
        console: '控制台',
        adventure: '冒险',
        stories: '自编故事',
        settings: '设置',
        menu: '菜单',
        logout: '退出',
      },
      header: {
        admin: '管理员',
        themeToDark: '切换暗色模式',
        themeToLight: '切换亮色模式',
        themeToSepia: '切换羊皮纸模式',
        switchToEnglish: 'Switch to English',
        switchToChinese: '切换为中文',
        font: '字体',
        fontSans: '现代无衬线 (Inter)',
        fontSerif: '古籍衬线 (思源宋体)',
        fontCn: '中文无衬线 (苹方 / 雅黑)',
        fontMono: '等宽 (JetBrains Mono)',
      },
      login: {
        title: '欢迎回到不存在之书',
        subtitle: 'Inkless — AI Interactive Narrative',
        tabLogin: '登录',
        tabRegister: '注册',
        usernameLabel: '用户名',
        usernamePlaceholder: '输入用户名',
        passwordLabel: '密码',
        passwordPlaceholder: '输入密码',
        submit: '登录',
        submitRegister: '注册',
        loading: '登录中…',
        invalid: '用户名或密码错误',
        empty: '请填写用户名和密码',
        toRegister: '没有账号？',
        toRegisterAction: '注册新账号',
        toLogin: '已有账号？',
        toLoginAction: '返回登录',
        failed: '操作失败',
      },
      common: {
        confirm: '确认',
        cancel: '取消',
        save: '保存',
        delete: '删除',
        edit: '编辑',
        loading: '加载中…',
        empty: '暂无数据',
      },
    },
  },
  'en-US': {
    translation: {
      app: {
        title: 'Inkless',
        subtitle: 'The Book That Never Was',
      },
      nav: {
        console: 'Console',
        adventure: 'Adventure',
        stories: 'Stories',
        settings: 'Settings',
        menu: 'Menu',
        logout: 'Logout',
      },
      header: {
        admin: 'Admin',
        themeToDark: 'Switch to dark mode',
        themeToLight: 'Switch to light mode',
        themeToSepia: 'Switch to sepia mode',
        switchToEnglish: 'Switch to English',
        switchToChinese: 'Switch to Chinese',
        font: 'Font',
        fontSans: 'Sans (Inter)',
        fontSerif: 'Serif (Source Han Serif)',
        fontCn: 'CN Sans (PingFang / YaHei)',
        fontMono: 'Mono (JetBrains Mono)',
      },
      login: {
        title: 'Welcome back to Inkless',
        subtitle: 'Inkless — AI Interactive Narrative',
        tabLogin: 'Sign in',
        tabRegister: 'Sign up',
        usernameLabel: 'Username',
        usernamePlaceholder: 'Enter username',
        passwordLabel: 'Password',
        passwordPlaceholder: 'Enter password',
        submit: 'Sign in',
        submitRegister: 'Sign up',
        loading: 'Signing in…',
        invalid: 'Invalid username or password',
        empty: 'Please enter username and password',
        toRegister: "Don't have an account?",
        toRegisterAction: 'Sign up',
        toLogin: 'Already have an account?',
        toLoginAction: 'Back to sign in',
        failed: 'Operation failed',
      },
      common: {
        confirm: 'Confirm',
        cancel: 'Cancel',
        save: 'Save',
        delete: 'Delete',
        edit: 'Edit',
        loading: 'Loading…',
        empty: 'No data',
      },
    },
  },
} as const;

function detectLanguage(): 'zh-CN' | 'en-US' {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === 'zh-CN' || saved === 'en-US') return saved;
  const nav = navigator.language || 'zh-CN';
  return nav.toLowerCase().startsWith('en') ? 'en-US' : 'zh-CN';
}

i18n.use(initReactI18next).init({
  resources,
  lng: detectLanguage(),
  fallbackLng: 'zh-CN',
  interpolation: { escapeValue: false },
  returnNull: false,
});

export function setLanguage(lang: 'zh-CN' | 'en-US') {
  localStorage.setItem(STORAGE_KEY, lang);
  i18n.changeLanguage(lang);
  document.documentElement.setAttribute('lang', lang);
}

document.documentElement.setAttribute('lang', i18n.language);

export default i18n;
