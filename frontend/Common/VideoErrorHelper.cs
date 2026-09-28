using MudBlazor;
using frontend.Models;

namespace frontend.Common;

public static class VideoErrorHelper
{
    public static string GetFriendlyError<T>(ApiResult<T>? result)
    {
        if (result is null)
            return "Không nhận được phản hồi từ máy chủ. Vui lòng thử lại.";

        return result.Code switch
        {
            CRUDStatusCodeRes.BAD_REQUEST           => "Thông tin không hợp lệ. Vui lòng kiểm tra lại.",
            CRUDStatusCodeRes.UNAUTHORIZED          => "Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.",
            CRUDStatusCodeRes.PAYMENT_REQUIRED      => "Không đủ Credit để tạo video.",
            CRUDStatusCodeRes.FORBIDDEN             => "Bạn không có quyền thực hiện thao tác này.",
            CRUDStatusCodeRes.NOT_FOUND             => "Không tìm thấy tài nguyên.",
            CRUDStatusCodeRes.CONFLICT              => "Bạn đang có job khác đang chạy. Vui lòng đợi hoàn tất.",
            CRUDStatusCodeRes.UNPROCESSABLE_ENTITY  => GetValidationMessage(result.Errors),
            CRUDStatusCodeRes.INTERNAL_SERVER_ERROR => "Máy chủ đang gặp sự cố. Vui lòng thử lại sau ít phút.",
            _                                       => "Có lỗi xảy ra. Vui lòng thử lại."
        };
    }

    public static string GetValidationMessage(Dictionary<string, List<string>>? errors)
    {
        if (errors is null || errors.Count == 0)
            return "Thông tin không hợp lệ. Vui lòng kiểm tra lại.";

        var firstField = errors.First();
        var firstError = firstField.Value.FirstOrDefault() ?? "không hợp lệ";

        return errors.Count == 1
            ? firstError
            : $"{firstError} (và {errors.Count - 1} lỗi khác)";
    }
}