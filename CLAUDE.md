# CLAUDE.md
# KỸ NĂNG (tóm tắt)

## 1. Suy nghĩ trước khi code
- Luôn nêu rõ giả định, hỏi nếu không chắc.
- Nếu có nhiều cách hiểu, hãy liệt kê, không tự chọn.
- Ưu tiên cách đơn giản, tránh phức tạp hóa.
- Nếu không rõ, dừng lại và hỏi.

## 2. Đơn giản là nhất
- Chỉ code tối thiểu để giải quyết yêu cầu.
- Không thêm tính năng ngoài yêu cầu.
- Không tạo abstraction nếu chỉ dùng 1 lần.
- Không xử lý lỗi cho trường hợp không thể xảy ra.
- Nếu code dài dòng, hãy rút gọn.

## 3. Thay đổi tối thiểu
- Chỉ sửa phần liên quan đến yêu cầu.
- Không chỉnh code, comment, format lân cận.
- Không refactor nếu không cần thiết.
- Giữ nguyên style cũ.
- Nếu tạo code thừa do sửa đổi, hãy xóa.
- Không xóa code chết có sẵn nếu không được yêu cầu.

## 4. Làm đến đâu xác minh đến đó
- Đặt tiêu chí thành công rõ ràng, kiểm tra sau mỗi bước.
- Nếu nhiều bước, hãy lên kế hoạch ngắn gọn.
- Tiêu chí mạnh giúp tự động hóa, tiêu chí yếu thì phải hỏi lại.


Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**


Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

When your changes create orphans:

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.


**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
