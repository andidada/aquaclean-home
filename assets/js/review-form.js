/* Customer review form
 * ------------------------------------------------------------------
 * Renders the "share your experience" block right under the testimonials grid
 * on the homepage and wires it to the review relay (assets/js/review-sink.js).
 *
 * Markup contract: the block ships as
 *   <section class="review-collect" data-review-collect>…</section>
 * with an empty <div data-review-mount></div>; this script fills in the form.
 * All copy is resolved from REVIEW_I18N at runtime, so there is one source of
 * truth for the nine languages instead of nine hand-edited HTML copies.
 */
(function () {
  var I18N = {
    en: {
      title: 'Share Your Experience',
      sub: 'Ordered from us? Tell other buyers what it was actually like.',
      name: 'Your name', company: 'Company (optional)', country: 'Country',
      product: 'Product line (optional)', rating: 'Your rating',
      content: 'Your review', contentPh: 'What did you order, how was the quality, delivery and communication?',
      submit: 'Submit review', sending: 'Sending...',
      ok: 'Thank you! Your review is with our team and will be published after a quick check.',
      fail: 'Sorry, your review could not be sent. Please try again in a moment.',
      needRating: 'Please choose a star rating.', needName: 'Please fill in your name.',
      needText: 'Please write a little more (at least 10 characters).',
      stars: ['1 star', '2 stars', '3 stars', '4 stars', '5 stars']
    },
    zh: {
      title: '分享你的使用体验',
      sub: '在我们这里下过单？告诉其他买家真实体验如何。',
      name: '你的姓名', company: '公司（选填）', country: '国家/地区',
      product: '产品线（选填）', rating: '你的评分',
      content: '评价内容', contentPh: '你采购了什么产品？质量、交期和沟通体验如何？',
      submit: '提交评价', sending: '提交中...',
      ok: '谢谢！评价已收到，我们快速审核后会公开展示。',
      fail: '抱歉，提交失败，请稍后重试。',
      needRating: '请先选择星级。', needName: '请填写姓名。',
      needText: '请再多写一点（至少 10 个字）。',
      stars: ['1 星', '2 星', '3 星', '4 星', '5 星']
    },
    ar: {
      title: 'شارك تجربتك',
      sub: 'اشتريت منّا؟ أخبر المشترين الآخرين عن تجربتك الحقيقية.',
      name: 'اسمك', company: 'الشركة (اختياري)', country: 'الدولة',
      product: 'خط المنتجات (اختياري)', rating: 'تقييمك',
      content: 'رأيك', contentPh: 'ماذا طلبت؟ وكيف كانت الجودة والتسليم والتواصل؟',
      submit: 'إرسال التقييم', sending: 'جارٍ الإرسال...',
      ok: 'شكرًا لك! وصلنا تقييمك وسننشره بعد مراجعة سريعة.',
      fail: 'عذرًا، لم نتمكن من الإرسال. يرجى المحاولة بعد قليل.',
      needRating: 'يرجى اختيار عدد النجوم.', needName: 'يرجى كتابة الاسم.',
      needText: 'يرجى كتابة المزيد (10 أحرف على الأقل).',
      stars: ['نجمة واحدة', 'نجمتان', '3 نجوم', '4 نجوم', '5 نجوم']
    },
    es: {
      title: 'Comparte tu experiencia',
      sub: '¿Compraste con nosotros? Cuéntale a otros compradores qué tal fue.',
      name: 'Tu nombre', company: 'Empresa (opcional)', country: 'País',
      product: 'Línea de producto (opcional)', rating: 'Tu valoración',
      content: 'Tu reseña', contentPh: '¿Qué pediste? ¿Cómo fueron la calidad, la entrega y la comunicación?',
      submit: 'Enviar reseña', sending: 'Enviando...',
      ok: '¡Gracias! Hemos recibido tu reseña y la publicaremos tras una revisión rápida.',
      fail: 'Lo sentimos, no se pudo enviar. Inténtalo de nuevo en un momento.',
      needRating: 'Elige una valoración con estrellas.', needName: 'Escribe tu nombre.',
      needText: 'Escribe un poco más (mínimo 10 caracteres).',
      stars: ['1 estrella', '2 estrellas', '3 estrellas', '4 estrellas', '5 estrellas']
    },
    fr: {
      title: 'Partagez votre expérience',
      sub: 'Vous avez commandé chez nous ? Racontez aux autres acheteurs ce que cela a donné.',
      name: 'Votre nom', company: 'Société (facultatif)', country: 'Pays',
      product: 'Gamme de produits (facultatif)', rating: 'Votre note',
      content: 'Votre avis', contentPh: 'Qu\'avez-vous commandé ? Qualité, livraison et communication ?',
      submit: 'Envoyer l\'avis', sending: 'Envoi...',
      ok: 'Merci ! Votre avis est reçu et sera publié après une vérification rapide.',
      fail: 'Désolé, l\'envoi a échoué. Merci de réessayer dans un instant.',
      needRating: 'Choisissez une note en étoiles.', needName: 'Indiquez votre nom.',
      needText: 'Écrivez un peu plus (10 caractères minimum).',
      stars: ['1 étoile', '2 étoiles', '3 étoiles', '4 étoiles', '5 étoiles']
    },
    id: {
      title: 'Bagikan Pengalaman Anda',
      sub: 'Pernah membeli dari kami? Ceritakan ke pembeli lain bagaimana hasilnya.',
      name: 'Nama Anda', company: 'Perusahaan (opsional)', country: 'Negara',
      product: 'Lini produk (opsional)', rating: 'Penilaian Anda',
      content: 'Ulasan Anda', contentPh: 'Apa yang Anda pesan? Bagaimana kualitas, pengiriman, dan komunikasinya?',
      submit: 'Kirim ulasan', sending: 'Mengirim...',
      ok: 'Terima kasih! Ulasan Anda sudah kami terima dan akan tayang setelah pemeriksaan singkat.',
      fail: 'Maaf, ulasan gagal terkirim. Silakan coba lagi sebentar.',
      needRating: 'Pilih penilaian bintang.', needName: 'Isi nama Anda.',
      needText: 'Tulis sedikit lebih panjang (minimal 10 karakter).',
      stars: ['1 bintang', '2 bintang', '3 bintang', '4 bintang', '5 bintang']
    },
    ru: {
      title: 'Поделитесь опытом',
      sub: 'Покупали у нас? Расскажите другим покупателям, как всё прошло.',
      name: 'Ваше имя', company: 'Компания (необязательно)', country: 'Страна',
      product: 'Линейка товаров (необязательно)', rating: 'Ваша оценка',
      content: 'Ваш отзыв', contentPh: 'Что вы заказывали? Как качество, сроки и общение?',
      submit: 'Отправить отзыв', sending: 'Отправляем...',
      ok: 'Спасибо! Отзыв получен, опубликуем его после короткой проверки.',
      fail: 'Не удалось отправить. Пожалуйста, попробуйте ещё раз через минуту.',
      needRating: 'Поставьте оценку звёздами.', needName: 'Укажите имя.',
      needText: 'Напишите чуть больше (минимум 10 символов).',
      stars: ['1 звезда', '2 звезды', '3 звезды', '4 звезды', '5 звёзд']
    },
    th: {
      title: 'แชร์ประสบการณ์ของคุณ',
      sub: 'เคยสั่งซื้อกับเรา? เล่าประสบการณ์ให้ผู้ซื้อคนอื่นฟัง',
      name: 'ชื่อของคุณ', company: 'บริษัท (ไม่บังคับ)', country: 'ประเทศ',
      product: 'กลุ่มสินค้า (ไม่บังคับ)', rating: 'คะแนนของคุณ',
      content: 'รีวิวของคุณ', contentPh: 'คุณสั่งซื้ออะไร คุณภาพ การจัดส่ง และการสื่อสารเป็นอย่างไร',
      submit: 'ส่งรีวิว', sending: 'กำลังส่ง...',
      ok: 'ขอบคุณ! เราได้รับรีวิวแล้ว และจะเผยแพร่หลังตรวจสอบเบื้องต้น',
      fail: 'ขออภัย ส่งไม่สำเร็จ กรุณาลองอีกครั้งในอีกสักครู่',
      needRating: 'กรุณาเลือกคะแนนดาว', needName: 'กรุณากรอกชื่อ',
      needText: 'กรุณาเขียนเพิ่มเติม (อย่างน้อย 10 ตัวอักษร)',
      stars: ['1 ดาว', '2 ดาว', '3 ดาว', '4 ดาว', '5 ดาว']
    },
    vi: {
      title: 'Chia sẻ trải nghiệm của bạn',
      sub: 'Đã mua từ chúng tôi? Hãy kể người mua khác biết trải nghiệm thực tế.',
      name: 'Tên của bạn', company: 'Công ty (không bắt buộc)', country: 'Quốc gia',
      product: 'Dòng sản phẩm (không bắt buộc)', rating: 'Đánh giá của bạn',
      content: 'Nhận xét của bạn', contentPh: 'Bạn đã đặt hàng gì? Chất lượng, giao hàng và trao đổi thông tin ra sao?',
      submit: 'Gửi nhận xét', sending: 'Đang gửi...',
      ok: 'Cảm ơn bạn! Chúng tôi đã nhận được nhận xét và sẽ đăng sau khi kiểm tra nhanh.',
      fail: 'Rất tiếc, gửi không thành công. Vui lòng thử lại sau giây lát.',
      needRating: 'Vui lòng chọn số sao.', needName: 'Vui lòng nhập tên.',
      needText: 'Vui lòng viết thêm một chút (tối thiểu 10 ký tự).',
      stars: ['1 sao', '2 sao', '3 sao', '4 sao', '5 sao']
    }
  };

  function dict() {
    var l = document.documentElement.lang;
    return I18N[l] || I18N.en;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function render(mount, t) {
    var stars = '';
    for (var i = 1; i <= 5; i++) {
      stars += '<label class="rc-star"><input type="radio" name="rating" value="' + i + '"' +
        (i === 5 ? ' checked' : '') + '><span aria-label="' + esc(t.stars[i - 1]) + '">★</span></label>';
    }
    mount.innerHTML =
      '<div class="rc-card">' +
        '<h3 class="rc-title">' + esc(t.title) + '</h3>' +
        '<p class="rc-sub">' + esc(t.sub) + '</p>' +
        '<form class="rc-form" novalidate>' +
          '<div class="rc-rating">' + stars + '</div>' +
          '<div class="rc-grid">' +
            '<label class="rc-field"><span>' + esc(t.name) + '</span>' +
              '<input type="text" name="author" maxlength="200" required></label>' +
            '<label class="rc-field"><span>' + esc(t.company) + '</span>' +
              '<input type="text" name="company" maxlength="300"></label>' +
            '<label class="rc-field"><span>' + esc(t.country) + '</span>' +
              '<input type="text" name="country" maxlength="80"></label>' +
            '<label class="rc-field"><span>' + esc(t.product) + '</span>' +
              '<input type="text" name="product_line" maxlength="200"></label>' +
          '</div>' +
          '<label class="rc-field rc-field-full"><span>' + esc(t.content) + '</span>' +
            '<textarea name="content" rows="4" maxlength="3000" required placeholder="' + esc(t.contentPh) + '"></textarea></label>' +
          '<input type="text" name="hp" class="rc-hp" tabindex="-1" autocomplete="off" aria-hidden="true">' +
          '<div class="rc-actions">' +
            '<button type="submit" class="rc-submit">' + esc(t.submit) + '</button>' +
            '<span class="rc-msg" data-review-msg role="status"></span>' +
          '</div>' +
        '</form>' +
      '</div>';
  }

  /* 星级点亮：纯 CSS 的兄弟选择器做不出「第 N 颗及之前全部点亮」，
     hover 方向也会反（~ 选的是后面的兄弟），所以用 JS 打 .is-lit。 */
  function paintStars(container, n) {
    var stars = container.querySelectorAll('.rc-star');
    for (var i = 0; i < stars.length; i++) {
      stars[i].classList.toggle('is-lit', i < n);
    }
  }

  function wireStars(form) {
    var box = form.querySelector('.rc-rating');
    if (!box) return;
    var stars = box.querySelectorAll('.rc-star');
    var repaint = function () {
      var c = form.querySelector('[name="rating"]:checked');
      paintStars(box, c ? parseInt(c.value, 10) : 0);
    };
    for (var i = 0; i < stars.length; i++) {
      (function (idx) {
        stars[idx].addEventListener('mouseenter', function () { paintStars(box, idx + 1); });
        stars[idx].addEventListener('focusin', function () { paintStars(box, idx + 1); });
      })(i);
    }
    box.addEventListener('mouseleave', repaint);
    box.addEventListener('focusout', repaint);
    form.addEventListener('change', function (e) {
      if (e.target && e.target.name === 'rating') repaint();
    });
    repaint();
  }

  function wire(form, t) {
    var msg = form.querySelector('[data-review-msg]');
    var btn = form.querySelector('.rc-submit');
    wireStars(form);
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var rating = form.querySelector('[name="rating"]:checked');
      var author = form.querySelector('[name="author"]');
      var content = form.querySelector('[name="content"]');
      if (!rating) { msg.textContent = t.needRating; return; }
      if (!author.value.trim()) { msg.textContent = t.needName; author.focus(); return; }
      if (content.value.trim().length < 10) { msg.textContent = t.needText; content.focus(); return; }
      btn.disabled = true;
      btn.textContent = t.sending;
      msg.textContent = '';
      var res = { ok: false };
      try {
        if (window.AQCReview) res = await window.AQCReview.submit(window.AQCReview.fromForm(form));
      } catch (err) { res = { ok: false }; }
      if (res && res.ok) {
        form.reset();
        var card = form.closest('.rc-card');
        if (card) {
          card.innerHTML = '<p class="rc-done">' + esc(t.ok) + '</p>';
        }
      } else {
        btn.disabled = false;
        btn.textContent = t.submit;
        msg.textContent = t.fail;
      }
    });
  }

  function init() {
    var mounts = document.querySelectorAll('[data-review-mount]');
    if (!mounts.length) return;
    var t = dict();
    for (var i = 0; i < mounts.length; i++) {
      render(mounts[i], t);
      var form = mounts[i].querySelector('form');
      if (form) wire(form, t);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
